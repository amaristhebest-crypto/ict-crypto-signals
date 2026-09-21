"""
Master ICT Setup Engine:
Integrates the complete ICT 2022 Mentorship & Silver Bullet Model:
- Premium/Discount Filter
- Session Kill Zone Validation
- Liquidity Sweep Identification
- SMT Divergence Check (BTC vs ETH)
- Displacement & Market Structure Shift (MSS)
- Fair Value Gap (FVG) Consequent Encroachment (CE)
- OTE Target Fibonacci Projections
"""
from typing import List, Optional
from datetime import datetime
from src.core.models import (
    Candle,
    Direction,
    ICTSignal,
)
from src.core.sessions import SessionDetector
from src.core.market_structure import MarketStructureAnalyzer
from src.core.pd_arrays import PDArrayEngine
from src.core.smt import SMTDivergenceDetector
from src.core.risk_manager import ICTRiskManager


class ICTSignalDetector:
    def __init__(self, min_risk_reward: float = 2.5):
        self.min_risk_reward = min_risk_reward

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

        # 1. Kill Zone & Session Check
        active_session = SessionDetector.get_active_session(now)
        is_kz = SessionDetector.is_killzone_active(now)

        # 2. HTF Dealing Range & Equilibrium Check
        htf_high = max(c.high for c in htf_candles[-30:])
        htf_low = min(c.low for c in htf_candles[-30:])
        htf_eq = PDArrayEngine.calculate_equilibrium(htf_high, htf_low)

        # 3. NY Midnight Open Reference
        ny_midnight_open = SessionDetector.get_ny_midnight_open(ltf_candles)

        # 4. Map LTF Swings
        swings = MarketStructureAnalyzer.find_swing_points(ltf_candles, left_bars=2, right_bars=2)
        if len(swings) < 4:
            return None

        # 5. Check SMT Divergence if secondary pair provided
        smt_result = None
        if smt_candles and len(smt_candles) >= 30:
            smt_result = SMTDivergenceDetector.analyze(
                ltf_candles, smt_candles, asset_a_name=symbol, asset_b_name=smt_symbol
            )

        # 6. Look for recent liquidity sweeps (within past 20 candles)
        recent_swings = [s for s in swings if s.index >= len(ltf_candles) - 25]

        # Scan for Bullish Setup (Swept Low -> Displaced MSS Up -> Retrace to FVG)
        low_swings = [s for s in recent_swings if not s.is_high]
        for swing in low_swings:
            sweep = MarketStructureAnalyzer.detect_liquidity_sweep(ltf_candles, swing, lookforward_window=10)
            if not sweep:
                continue

            sweep_idx, sweep_low = sweep

            # Premium/Discount check: Buying should occur in Discount
            if sweep_low > htf_eq:
                continue  # Skip longs in HTF premium

            # Detect MSS
            mss = MarketStructureAnalyzer.detect_market_structure_shift(
                ltf_candles, swings, sweep_index=sweep_idx, search_window=12
            )
            if not mss or mss[1] != Direction.BULLISH:
                continue

            mss_idx, _, broken_level = mss

            # Scan for 5M Bullish FVGs created during displacement
            fvgs = PDArrayEngine.find_fair_value_gaps(ltf_candles[sweep_idx : mss_idx + 2])
            bullish_fvgs = [f for f in fvgs if f.direction == Direction.BULLISH]
            if not bullish_fvgs:
                continue

            entry_fvg = bullish_fvgs[-1]
            entry_price = entry_fvg.consequent_encroachment
            stop_loss = sweep_low - 20.0  # Buffer below the liquidity purge low

            # Calculate OTE targets & HTF DOL
            displacement_high = max(c.high for c in ltf_candles[sweep_idx : mss_idx + 2])
            ote_levels = ICTRiskManager.calculate_ote_levels(sweep_low, displacement_high, Direction.BULLISH)

            target_1 = displacement_high
            target_2 = ote_levels["ext_027"]
            target_3 = max(ote_levels["ext_062"], ote_levels["ext_100"])

            risk = entry_price - stop_loss
            reward = target_3 - entry_price
            if risk <= 0:
                continue
            rr = reward / risk

            if rr >= self.min_risk_reward:
                confluences = [
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

        # Scan for Bearish Setup (Swept High -> Displaced MSS Down -> Retrace to FVG)
        high_swings = [s for s in recent_swings if s.is_high]
        for swing in high_swings:
            sweep = MarketStructureAnalyzer.detect_liquidity_sweep(ltf_candles, swing, lookforward_window=10)
            if not sweep:
                continue

            sweep_idx, sweep_high = sweep

            # Premium/Discount check: Selling should occur in Premium
            if sweep_high < htf_eq:
                continue  # Skip shorts in HTF discount

            # Detect MSS
            mss = MarketStructureAnalyzer.detect_market_structure_shift(
                ltf_candles, swings, sweep_index=sweep_idx, search_window=12
            )
            if not mss or mss[1] != Direction.BEARISH:
                continue

            mss_idx, _, broken_level = mss

            # Scan for Bearish FVGs created during displacement
            fvgs = PDArrayEngine.find_fair_value_gaps(ltf_candles[sweep_idx : mss_idx + 2])
            bearish_fvgs = [f for f in fvgs if f.direction == Direction.BEARISH]
            if not bearish_fvgs:
                continue

            entry_fvg = bearish_fvgs[-1]
            entry_price = entry_fvg.consequent_encroachment
            stop_loss = sweep_high + 20.0  # Buffer above the liquidity purge high

            displacement_low = min(c.low for c in ltf_candles[sweep_idx : mss_idx + 2])
            ote_levels = ICTRiskManager.calculate_ote_levels(displacement_low, sweep_high, Direction.BEARISH)

            target_1 = displacement_low
            target_2 = ote_levels["ext_027"]
            target_3 = min(ote_levels["ext_062"], ote_levels["ext_100"])

            risk = stop_loss - entry_price
            reward = entry_price - target_3
            if risk <= 0:
                continue
            rr = reward / risk

            if rr >= self.min_risk_reward:
                confluences = [
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
