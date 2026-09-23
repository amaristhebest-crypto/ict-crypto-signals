"""
Master ICT Setup Engine.

FIXED 2026-09-23 — four correctness bugs plus a diagnostic funnel:

  C4  Bounce counting was per-candle, not per-visit. Three consecutive candles
      inside an FVG registered as 3 bounces and the setup was discarded — but
      three candles inside the gap is exactly what a fill looks like. Now
      edge-triggered: one bounce per visit.

  C5  Risk:Reward was computed against target_3 (the -1.00 extension) while the
      alert instructs you to take profit at target_2 (-0.272). At the FVG
      midpoint that displayed 3.0:1 for a trade that was really 1.54:1, and the
      min_risk_reward gate was measuring the wrong thing entirely.

  C6  The bullish loop returned on first match, so the bearish block was only
      reached if no long existed anywhere. Now both directions are scanned,
      candidates collected, and the best R:R wins.

  H7  detect_market_structure_shift is now called with required_direction, so a
      counter-direction shift can no longer kill a valid setup.

  NEW Rejection funnel counters. Call reset_rejections() at the start of a scan
      and read REJECTIONS afterwards to see which stage is discarding setups.
"""
from typing import List, Optional, Dict, Any

from src.core.models import (
    Candle,
    Direction,
    ICTSignal,
    FairValueGap,
)
from src.core.sessions import SessionDetector
from src.core.market_structure import MarketStructureAnalyzer
from src.core.pd_arrays import PDArrayEngine
from src.core.smt import SMTDivergenceDetector
from src.core.risk_manager import ICTRiskManager


# --------------------------------------------------------------------------
# Diagnostic funnel. Nine stages can discard a setup; without this you cannot
# tell whether silence is discipline or a bug.
# --------------------------------------------------------------------------
REJECTIONS: Dict[str, int] = {}


def _rej(reason: str) -> None:
    REJECTIONS[reason] = REJECTIONS.get(reason, 0) + 1


def reset_rejections() -> None:
    REJECTIONS.clear()


class ICTSignalDetector:
    def __init__(self, min_risk_reward: float = 2.5, enforce_killzone: bool = True):
        self.min_risk_reward = min_risk_reward
        self.enforce_killzone = enforce_killzone

    # ----------------------------------------------------------------------
    @staticmethod
    def audit_fvg_lifecycle(
        fvg: FairValueGap, subsequent_candles: List[Candle], target_1: float, direction: Direction
    ) -> Dict:
        """
        Ep 41 two-bounce rule, Ep 6/15 close-through invalidation, Ep 40 runaway
        protection.

        FIXED: bounces are now EDGE-TRIGGERED. A bounce is counted only when
        price ENTERS the gap having previously been outside it. Consecutive
        candles resting inside the gap count once, which is what "bounce" means.
        """
        bounces = 0
        closed_through = False
        hit_target_first = False
        currently_inside = False
        was_inside = False

        last_idx = len(subsequent_candles) - 1

        for idx, c in enumerate(subsequent_candles):
            if direction == Direction.BULLISH:
                # Runaway expansion: price reached target 1 without ever retracing
                if bounces == 0 and c.high >= target_1 and c.low > fvg.top:
                    hit_target_first = True
                    break
                # Invalidation: body closed below the gap
                if c.close < fvg.bottom:
                    closed_through = True
                    break
                overlapping = c.low <= fvg.top and c.high >= fvg.bottom
            else:
                if bounces == 0 and c.low <= target_1 and c.high < fvg.bottom:
                    hit_target_first = True
                    break
                if c.close > fvg.top:
                    closed_through = True
                    break
                overlapping = c.high >= fvg.bottom and c.low <= fvg.top

            if overlapping and not was_inside:
                bounces += 1
            was_inside = overlapping

            if overlapping and idx == last_idx:
                currently_inside = True

        return {
            "bounces": bounces,
            "closed_through": closed_through,
            "hit_target_first": hit_target_first,
            "currently_inside": currently_inside,
            "is_valid": not closed_through and not hit_target_first and bounces <= 2,
        }

    # ----------------------------------------------------------------------
    def _scan(
        self,
        direction: Direction,
        ltf_candles: List[Candle],
        swings: List,
        recent_swings: List,
        htf_eq: float,
    ) -> List[Dict[str, Any]]:
        """
        Scans one direction and returns every qualifying candidate.
        Does NOT return early — that was the source of the long-side bias.
        """
        bullish = direction == Direction.BULLISH
        candidates: List[Dict[str, Any]] = []
        side = "long" if bullish else "short"

        # Longs hunt swept LOWS (sell-side liquidity); shorts hunt swept HIGHS.
        pool = [s for s in recent_swings if s.is_high != bullish]

        for swing in pool:
            sweep = MarketStructureAnalyzer.detect_liquidity_sweep(
                ltf_candles, swing, lookforward_window=10
            )
            if not sweep:
                _rej(f"{side}: swing never swept")
                continue

            sweep_idx, sweep_px = sweep

            # Premium / discount. NOTE: measured on the SWEEP price, not the
            # entry price. Ep 13 says the ENTRY must be at a discount. Left
            # as-is to avoid changing signal volume in the same pass as the
            # correctness fixes — see FIXES.md "still open".
            if bullish and sweep_px > htf_eq:
                _rej("long: sweep not in discount")
                continue
            if not bullish and sweep_px < htf_eq:
                _rej("short: sweep not in premium")
                continue

            mss = MarketStructureAnalyzer.detect_market_structure_shift(
                ltf_candles,
                swings,
                sweep_index=sweep_idx,
                search_window=12,
                required_direction=direction,
            )
            if not mss:
                _rej(f"{side}: no MSS after sweep")
                continue

            mss_idx, _, broken_level = mss

            window = ltf_candles[sweep_idx: mss_idx + 2]
            fvgs = [f for f in PDArrayEngine.find_fair_value_gaps(window) if f.direction == direction]
            if not fvgs:
                _rej(f"{side}: no FVG in displacement")
                continue

            entry_fvg = fvgs[-1]
            entry_price = entry_fvg.consequent_encroachment

            buffer = max(abs(sweep_px) * 0.0005, 0.05)
            stop_loss = sweep_px - buffer if bullish else sweep_px + buffer

            if bullish:
                displacement_extreme = max(c.high for c in window)
                ote = ICTRiskManager.calculate_ote_levels(sweep_px, displacement_extreme, Direction.BULLISH)
            else:
                displacement_extreme = min(c.low for c in window)
                ote = ICTRiskManager.calculate_ote_levels(displacement_extreme, sweep_px, Direction.BEARISH)

            target_1 = displacement_extreme
            target_2 = ote["ext_027"]
            target_3 = ote["ext_100"]   # ext_062 is unreachable by construction

            global_fvg_idx = sweep_idx + entry_fvg.candle_index
            subsequent = ltf_candles[global_fvg_idx + 2:]
            lifecycle = self.audit_fvg_lifecycle(entry_fvg, subsequent, target_1, direction)

            if not lifecycle["is_valid"]:
                if lifecycle["closed_through"]:
                    _rej(f"{side}: FVG closed through")
                elif lifecycle["hit_target_first"]:
                    _rej(f"{side}: runaway, target hit before retrace")
                else:
                    _rej(f"{side}: FVG exhausted ({lifecycle['bounces']} bounces)")
                continue

            ob = PDArrayEngine.find_order_block(
                ltf_candles, displacement_index=mss_idx, direction=direction
            )
            if ob:
                breached = any(c.close < ob.mean_threshold for c in subsequent) if bullish \
                    else any(c.close > ob.mean_threshold for c in subsequent)
                if breached:
                    _rej(f"{side}: order block mean threshold breached")
                    continue

            risk = (entry_price - stop_loss) if bullish else (stop_loss - entry_price)
            if risk <= 0:
                _rej(f"{side}: non-positive risk")
                continue

            # FIXED (C5): reward measured against target_2, which is the take
            # profit the alert actually instructs. Previously target_3.
            reward = (target_2 - entry_price) if bullish else (entry_price - target_2)
            rr = reward / risk

            if rr < self.min_risk_reward:
                _rej(f"{side}: R:R {rr:.2f} below {self.min_risk_reward}")
                continue

            candidates.append({
                "direction": direction,
                "swing": swing,
                "sweep_px": sweep_px,
                "broken_level": broken_level,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target_1": target_1,
                "target_2": target_2,
                "target_3": target_3,
                "rr": rr,
                "lifecycle": lifecycle,
                "mss_idx": mss_idx,
            })

        return candidates

    # ----------------------------------------------------------------------
    def analyze_market(
        self,
        symbol: str,
        ltf_candles: List[Candle],
        htf_candles: List[Candle],
        smt_candles: Optional[List[Candle]] = None,
        smt_symbol: str = "ETH/USDT",
        timeframe: str = "5m",
    ) -> Optional[ICTSignal]:
        if len(ltf_candles) < 30 or len(htf_candles) < 15:
            _rej("insufficient candle history")
            return None

        current_candle = ltf_candles[-1]
        now = current_candle.timestamp

        active_session = SessionDetector.get_active_session(now)
        if self.enforce_killzone and not SessionDetector.is_killzone_active(now):
            _rej("outside killzone: " + active_session.split("(")[0].strip())
            return None

        htf_high = max(c.high for c in htf_candles[-30:])
        htf_low = min(c.low for c in htf_candles[-30:])
        htf_eq = PDArrayEngine.calculate_equilibrium(htf_high, htf_low)

        ny_midnight_open = SessionDetector.get_ny_midnight_open(ltf_candles)

        swings = MarketStructureAnalyzer.find_swing_points(ltf_candles, left_bars=2, right_bars=2)
        if len(swings) < 4:
            _rej("fewer than 4 swing points")
            return None

        smt_result = None
        if smt_candles and len(smt_candles) >= 30:
            smt_result = SMTDivergenceDetector.analyze(
                ltf_candles, smt_candles, asset_a_name=symbol, asset_b_name=smt_symbol
            )

        recent_swings = [s for s in swings if s.index >= len(ltf_candles) - 25]

        # FIXED (C6): both directions scanned, no early return.
        candidates = self._scan(Direction.BULLISH, ltf_candles, swings, recent_swings, htf_eq)
        candidates += self._scan(Direction.BEARISH, ltf_candles, swings, recent_swings, htf_eq)

        if not candidates:
            return None

        best = max(candidates, key=lambda c: c["rr"])
        bullish = best["direction"] == Direction.BULLISH
        lc = best["lifecycle"]

        status_str = (
            "TRIGGERED / PRICE CURRENTLY INSIDE FVG"
            if lc["currently_inside"]
            else "PENDING LIMIT ORDER AT CE"
        )

        confluences = [
            f"Order State: {status_str} (Bounce count: {lc['bounces']}/2)",
            f"HTF Dealing Range {'Discount' if bullish else 'Premium'} "
            f"(EQ {htf_eq:.2f} from {len(htf_candles[-30:])} HTF bars)",
            f"Session: {active_session}",
            f"Liquidity Sweep of resting {'SSL' if bullish else 'BSL'} at "
            f"{best['swing'].price:.2f} (Wick to {best['sweep_px']:.2f})",
            f"Market Structure Shift confirmed with body displacement "
            f"{'above' if bullish else 'below'} {best['broken_level']:.2f}",
            f"Entry at FVG Consequent Encroachment (50% = {best['entry_price']:.2f})",
        ]

        if ny_midnight_open is not None:
            if (bullish and current_candle.close < ny_midnight_open) or \
               ((not bullish) and current_candle.close > ny_midnight_open):
                confluences.append(
                    f"Price is trading {'below' if bullish else 'above'} "
                    f"NY Midnight Open ({ny_midnight_open:.2f})"
                )

        if smt_result and smt_result.detected and smt_result.direction == best["direction"]:
            confluences.append(f"SMT Divergence Confirmed: {smt_result.description}")

        return ICTSignal(
            symbol=symbol,
            timeframe=timeframe,
            direction=best["direction"],
            setup_name=f"ICT 2022 Mentorship {'Long' if bullish else 'Short'} + FVG CE",
            session_name=active_session,
            timestamp=current_candle.timestamp,
            entry_price=round(best["entry_price"], 2),
            stop_loss=round(best["stop_loss"], 2),
            target_1=round(best["target_1"], 2),
            target_2=round(best["target_2"], 2),
            target_3=round(best["target_3"], 2),
            risk_reward_ratio=round(best["rr"], 2),
            invalidation_notes=(
                "Invalidated if a candle body closes beyond the sweep extreme "
                "or the Order Block Mean Threshold."
            ),
            confluence_factors=confluences,
        )
