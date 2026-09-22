"""
Master ICT Setup Engine:
Integrates the complete ICT 2022 Mentorship Program (Episodes 1 to 41) & Core Content:
- Strict Kill Zone & No-Trade NY Lunch (12:00-13:00 EST) Dead Zone Filter (Ep 5 & 39)
- Pre-08:30 AM EST Swing High/Low Sweep Anchors (Ep 4 & 5)
- Premium/Discount 50% Equilibrium Filter (Ep 2 & 29)
- Liquidity Sweep Identification (Wick only vs Body Displacement MSS) (Ep 2 & 6)
- SMT Divergence Check (BTC vs ETH) (Ep 29 & 30)
- Fair Value Gap (FVG) Consequent Encroachment (CE: 50% midpoint) (Ep 2, 6, 38)
- 2-Bounce FVG Exhaustion Rule (Ep 41: Max 2 bounces allowed, 3rd tap fails)
- Inversion / Close-Through FVG Invalidation (Ep 6 & 15)
- Runaway Expansion Protection (Do not chase if Target 1 hit prior to retrace) (Ep 40)
- Order Block Mean Threshold Invalidation (Ep 13 & 33)
- OTE Target Fibonacci Projections (-0.27, -0.62, -1.00) (Ep 2 & Ref Guide)
"""
from typing import List, Optional, Tuple, Dict
from datetime import datetime, time
import zoneinfo

from src.core.models import (
    Candle,
    Direction,
    ICTSignal,
    FairValueGap,
)
from src.core.sessions import SessionDetector, NY_TZ
from src.core.market_structure import MarketStructureAnalyzer
from src.core.pd_arrays import PDArrayEngine
from src.core.smt import SMTDivergenceDetector
from src.core.risk_manager import ICTRiskManager


# --- diagnostic funnel counters -------------------------------------------
REJECTIONS = {}


def _rej(reason: str):
    REJECTIONS[reason] = REJECTIONS.get(reason, 0) + 1


def reset_rejections():
    REJECTIONS.clear()
# ---------------------------------------------------------------------------


class ICTSignalDetector:
    def __init__(self, min_risk_reward: float = 2.5, enforce_killzone: bool = True):
        self.min_risk_reward = min_risk_reward
        self.enforce_killzone = enforce_killzone

    @staticmethod
    def audit_fvg_lifecycle(
        fvg: FairValueGap, subsequent_candles: List[Candle], target_1: float, direction: Direction
    ) -> Dict:
        """
        Enforces Huddleston's explicit FVG lifecycle rules:
        1. Episode 41: 2-Bounce Rule (Price can bounce max 2 times; 3rd tap is exhausted).
        2. Episode 6 & 15: Invalidation if candle body closes beyond the FVG boundary.
        3. Episode 40: Runaway expansion protection (Do not enter if price hits Target 1 before retracing).
        """
        bounces = 0
        closed_through = False
        hit_target_first = False
        currently_inside = False
        was_inside = False

        for idx, c in enumerate(subsequent_candles):
            if direction == Direction.BULLISH:
                # Check runaway expansion
                if bounces == 0 and c.high >= target_1 and c.low > fvg.top:
                    hit_target_first = True
                    break
                # Check invalidation (candle body close below FVG bottom)
                if c.close < fvg.bottom:
                    closed_through = True
                    break
                # Check touch / bounce inside FVG (edge-triggered: one bounce per visit)
                overlapping = c.low <= fvg.top and c.high >= fvg.bottom
                if overlapping and not was_inside:
                    bounces += 1
                was_inside = overlapping
                if overlapping and idx == len(subsequent_candles) - 1:
                    currently_inside = True
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
                if overlapping and idx == len(subsequent_candles) - 1:
                    currently_inside = True

        return {
            "bounces": bounces,
            "closed_through": closed_through,
            "hit_target_first": hit_target_first,
            "currently_inside": currently_inside,
            "is_valid": not closed_through and not hit_target_first and bounces <= 2,
        }

    def analyze_market(
        self,
        symbol: str,
        ltf_candles: List[Candle],
        htf_candles: List[Candle],
        smt_candles: Optional[List[Candle]] = None,
        smt_symbol: str = "ETH/USDT",
        timeframe: str = "5m",
    ) -> Optional[ICTSignal]:
        """
        Executes complete institutional pipeline on incoming candle stream.
        """
        if len(ltf_candles) < 30 or len(htf_candles) < 15:
            return None

        current_candle = ltf_candles[-1]
        now = current_candle.timestamp

        # 1. Kill Zone & NY Lunch Dead Zone Check (Ep 5 & 39)
        active_session = SessionDetector.get_active_session(now)
        is_kz = SessionDetector.is_killzone_active(now)

        if self.enforce_killzone and not is_kz:
            # Strictly reject setups outside valid kill zones or during NY lunch dead zone
            _rej(f"outside killzone ({active_session[:40]})")
            return None

        # 2. HTF Dealing Range & Equilibrium Check (Ep 2 & 29)
        htf_high = max(c.high for c in htf_candles[-30:])
        htf_low = min(c.low for c in htf_candles[-30:])
        htf_eq = PDArrayEngine.calculate_equilibrium(htf_high, htf_low)

        # 3. NY Midnight Open Reference (Ep 11 & 16)
        ny_midnight_open = SessionDetector.get_ny_midnight_open(ltf_candles)

        # 4. Map LTF Swings
        swings = MarketStructureAnalyzer.find_swing_points(ltf_candles, left_bars=2, right_bars=2)
        if len(swings) < 4:
            _rej("fewer than 4 swing points")
            return None

        # 5. Check SMT Divergence if secondary pair provided (Ep 29 & 30)
        smt_result = None
        if smt_candles and len(smt_candles) >= 30:
            smt_result = SMTDivergenceDetector.analyze(
                ltf_candles, smt_candles, asset_a_name=symbol, asset_b_name=smt_symbol
            )

        # 6. Scan for Sweeps of Recent Swings
        recent_swings = [s for s in swings if s.index >= len(ltf_candles) - 25]

        # =========================================================================
        # BULLISH SETUP (Sweep SSL -> Displaced MSS Up -> FVG Retest at CE)
        # =========================================================================
        low_swings = [s for s in recent_swings if not s.is_high]
        for swing in low_swings:
            sweep = MarketStructureAnalyzer.detect_liquidity_sweep(ltf_candles, swing, lookforward_window=10)
            if not sweep:
                continue

            sweep_idx, sweep_low = sweep

            # Premium/Discount check: Longs permitted ONLY in Discount (< 50% EQ)
            if sweep_low > htf_eq:
                _rej("long rejected: not in discount")
                continue

            # Detect MSS (Full body closure with displacement above swing high)
            mss = MarketStructureAnalyzer.detect_market_structure_shift(
                ltf_candles, swings, sweep_index=sweep_idx, search_window=12,
                required_direction=Direction.BULLISH
            )
            if not mss:
                _rej("no bullish MSS after sweep")
                continue

            mss_idx, _, broken_level = mss

            # Scan for 5M Bullish FVGs created during displacement
            fvgs = PDArrayEngine.find_fair_value_gaps(ltf_candles[sweep_idx : mss_idx + 2])
            bullish_fvgs = [f for f in fvgs if f.direction == Direction.BULLISH]
            if not bullish_fvgs:
                _rej("no bullish FVG in displacement")
                continue

            entry_fvg = bullish_fvgs[-1]
            entry_price = entry_fvg.consequent_encroachment
            # Asset-adaptive protective stop buffer (0.05% of price or min tick buffer)
            buffer = max(sweep_low * 0.0005, 0.05)
            stop_loss = sweep_low - buffer  # Conservative stop below sweep low (Ep 6)

            # Calculate OTE targets & HTF DOL
            displacement_high = max(c.high for c in ltf_candles[sweep_idx : mss_idx + 2])
            ote_levels = ICTRiskManager.calculate_ote_levels(sweep_low, displacement_high, Direction.BULLISH)

            target_1 = displacement_high
            target_2 = ote_levels["ext_027"]
            target_3 = max(ote_levels["ext_062"], ote_levels["ext_100"])

            # 7. Audit FVG Lifecycle (Ep 41 2-Bounce Rule & Runaway Protection)
            global_fvg_idx = sweep_idx + entry_fvg.candle_index
            subsequent_candles = ltf_candles[global_fvg_idx + 2 :]
            lifecycle = self.audit_fvg_lifecycle(entry_fvg, subsequent_candles, target_1, Direction.BULLISH)

            if not lifecycle["is_valid"]:
                if lifecycle["closed_through"]:
                    _rej("FVG closed through")
                elif lifecycle["hit_target_first"]:
                    _rej("runaway: hit target before retrace")
                else:
                    _rej(f"FVG exhausted ({lifecycle['bounces']} bounces)")
                continue

            # 8. Check Order Block Mean Threshold Invalidation (Ep 13 & 33)
            ob = PDArrayEngine.find_order_block(ltf_candles, displacement_index=mss_idx, direction=Direction.BULLISH)
            if ob:
                # If any candle body closed below OB Mean Threshold, invalidate
                if any(c.close < ob.mean_threshold for c in subsequent_candles):
                    _rej("bullish OB mean threshold violated")
                    continue

            risk = entry_price - stop_loss
            reward = target_2 - entry_price
            if risk <= 0:
                _rej("non-positive risk (bullish)")
                continue
            rr = reward / risk

            if rr < self.min_risk_reward:
                _rej(f"R:R {rr:.2f} below {self.min_risk_reward}")

            if rr >= self.min_risk_reward:
                status_str = (
                    "TRIGGERED / PRICE CURRENTLY INSIDE FVG"
                    if lifecycle["currently_inside"]
                    else "PENDING LIMIT ORDER AT CE"
                )
                confluences = [
                    f"Order State: {status_str} (Bounce count: {lifecycle['bounces']}/2)",
                    f"4H Dealing Range Discount (Price below EQ {htf_eq:.2f})",
                    f"Session: {active_session}",
                    f"Liquidity Sweep of resting SSL at {swing.price:.2f} (Wick to {sweep_low:.2f})",
                    f"Market Structure Shift confirmed with candle body displacement above {broken_level:.2f}",
                    f"Entry at 5M Bullish FVG Consequent Encroachment (50% = {entry_price:.2f})",
                ]
                if current_candle.close < ny_midnight_open:
                    confluences.append(f"Price is trading below NY Midnight Open ({ny_midnight_open:.2f})")
                if smt_result and smt_result.detected and smt_result.direction == Direction.BULLISH:
                    confluences.append(f"SMT Divergence Confirmed: {smt_result.description}")

                return ICTSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=Direction.BULLISH,
                    setup_name="ICT 2022 Mentorship Long + FVG CE",
                    session_name=active_session,
                    timestamp=current_candle.timestamp,
                    entry_price=round(entry_price, 2),
                    stop_loss=round(stop_loss, 2),
                    target_1=round(target_1, 2),
                    target_2=round(target_2, 2),
                    target_3=round(target_3, 2),
                    risk_reward_ratio=round(rr, 2),
                    invalidation_notes="Invalidated if candle body closes below the sweep low or Order Block Mean Threshold.",
                    confluence_factors=confluences,
                )

        # =========================================================================
        # BEARISH SETUP (Sweep BSL -> Displaced MSS Down -> FVG Retest at CE)
        # =========================================================================
        high_swings = [s for s in recent_swings if s.is_high]
        for swing in high_swings:
            sweep = MarketStructureAnalyzer.detect_liquidity_sweep(ltf_candles, swing, lookforward_window=10)
            if not sweep:
                continue

            sweep_idx, sweep_high = sweep

            # Premium/Discount check: Shorts permitted ONLY in Premium (> 50% EQ)
            if sweep_high < htf_eq:
                _rej("short rejected: not in premium")
                continue

            # Detect MSS
            mss = MarketStructureAnalyzer.detect_market_structure_shift(
                ltf_candles, swings, sweep_index=sweep_idx, search_window=12,
                required_direction=Direction.BEARISH
            )
            if not mss:
                _rej("no bearish MSS after sweep")
                continue

            mss_idx, _, broken_level = mss

            # Scan for Bearish FVGs created during displacement
            fvgs = PDArrayEngine.find_fair_value_gaps(ltf_candles[sweep_idx : mss_idx + 2])
            bearish_fvgs = [f for f in fvgs if f.direction == Direction.BEARISH]
            if not bearish_fvgs:
                _rej("no bearish FVG in displacement")
                continue

            entry_fvg = bearish_fvgs[-1]
            entry_price = entry_fvg.consequent_encroachment
            # Asset-adaptive protective stop buffer (0.05% of price or min tick buffer)
            buffer = max(sweep_high * 0.0005, 0.05)
            stop_loss = sweep_high + buffer

            displacement_low = min(c.low for c in ltf_candles[sweep_idx : mss_idx + 2])
            ote_levels = ICTRiskManager.calculate_ote_levels(displacement_low, sweep_high, Direction.BEARISH)

            target_1 = displacement_low
            target_2 = ote_levels["ext_027"]
            target_3 = min(ote_levels["ext_062"], ote_levels["ext_100"])

            # 7. Audit FVG Lifecycle
            global_fvg_idx = sweep_idx + entry_fvg.candle_index
            subsequent_candles = ltf_candles[global_fvg_idx + 2 :]
            lifecycle = self.audit_fvg_lifecycle(entry_fvg, subsequent_candles, target_1, Direction.BEARISH)

            if not lifecycle["is_valid"]:
                if lifecycle["closed_through"]:
                    _rej("FVG closed through")
                elif lifecycle["hit_target_first"]:
                    _rej("runaway: hit target before retrace")
                else:
                    _rej(f"FVG exhausted ({lifecycle['bounces']} bounces)")
                continue

            # 8. Check Order Block Mean Threshold Invalidation
            ob = PDArrayEngine.find_order_block(ltf_candles, displacement_index=mss_idx, direction=Direction.BEARISH)
            if ob:
                if any(c.close > ob.mean_threshold for c in subsequent_candles):
                    _rej("bearish OB mean threshold violated")
                    continue

            risk = stop_loss - entry_price
            reward = entry_price - target_2
            if risk <= 0:
                _rej("non-positive risk (bearish)")
                continue
            rr = reward / risk

            if rr < self.min_risk_reward:
                _rej(f"R:R {rr:.2f} below {self.min_risk_reward}")

            if rr >= self.min_risk_reward:
                status_str = (
                    "TRIGGERED / PRICE CURRENTLY INSIDE FVG"
                    if lifecycle["currently_inside"]
                    else "PENDING LIMIT ORDER AT CE"
                )
                confluences = [
                    f"Order State: {status_str} (Bounce count: {lifecycle['bounces']}/2)",
                    f"4H Dealing Range Premium (Price above EQ {htf_eq:.2f})",
                    f"Session: {active_session}",
                    f"Liquidity Sweep of resting BSL at {swing.price:.2f} (Wick to {sweep_high:.2f})",
                    f"Market Structure Shift confirmed with candle body displacement below {broken_level:.2f}",
                    f"Entry at 5M Bearish FVG Consequent Encroachment (50% = {entry_price:.2f})",
                ]
                if current_candle.close > ny_midnight_open:
                    confluences.append(f"Price is trading above NY Midnight Open ({ny_midnight_open:.2f})")
                if smt_result and smt_result.detected and smt_result.direction == Direction.BEARISH:
                    confluences.append(f"SMT Divergence Confirmed: {smt_result.description}")

                return ICTSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=Direction.BEARISH,
                    setup_name="ICT 2022 Mentorship Short + FVG CE",
                    session_name=active_session,
                    timestamp=current_candle.timestamp,
                    entry_price=round(entry_price, 2),
                    stop_loss=round(stop_loss, 2),
                    target_1=round(target_1, 2),
                    target_2=round(target_2, 2),
                    target_3=round(target_3, 2),
                    risk_reward_ratio=round(rr, 2),
                    invalidation_notes="Invalidated if candle body closes above the sweep high or Order Block Mean Threshold.",
                    confluence_factors=confluences,
                )

        return None
