"""
Institutional Market Structure:
- 3-bar Short-Term Highs (STH) and Lows (STL)
- Intermediate-Term Highs (ITH) and Lows (ITL)
- Liquidity Sweeps (Wick only: "Wicks do the damage")
- Market Structure Shifts (MSS) (Full body closures: "Bodies tell the story")
- Displacement Candle Validation
"""
from typing import List, Tuple, Optional
from src.core.models import Candle, SwingPoint, Direction


class MarketStructureAnalyzer:
    @staticmethod
    def find_swing_points(candles: List[Candle], left_bars: int = 2, right_bars: int = 2) -> List[SwingPoint]:
        """
        Identifies valid swing points using 3-to-5 bar fractal formation.
        """
        swings: List[SwingPoint] = []
        n = len(candles)

        for i in range(left_bars, n - right_bars):
            curr = candles[i]

            # Swing High
            is_high = True
            for j in range(i - left_bars, i + right_bars + 1):
                if j != i and candles[j].high >= curr.high:
                    is_high = False
                    break
            if is_high:
                swings.append(SwingPoint(index=i, timestamp=curr.timestamp, price=curr.high, is_high=True))
                continue

            # Swing Low
            is_low = True
            for j in range(i - left_bars, i + right_bars + 1):
                if j != i and candles[j].low <= curr.low:
                    is_low = False
                    break
            if is_low:
                swings.append(SwingPoint(index=i, timestamp=curr.timestamp, price=curr.low, is_high=False))

        return swings

    @staticmethod
    def detect_liquidity_sweep(
        candles: List[Candle], swing: SwingPoint, lookforward_window: int = 15
    ) -> Optional[Tuple[int, float]]:
        """
        Checks if a swing high or low was swept by a wick or an immediate rejection.
        - High sweep: price trades higher than swing high, but candle body closes below
          or subsequent candle promptly trades back below the swing level.
        - Low sweep: price trades lower than swing low, but candle body closes above
          or subsequent candle promptly trades back above the swing level.
        Returns (candle_index, sweep_extreme_price) if swept, else None.
        """
        start_idx = swing.index + 1
        end_idx = min(len(candles), start_idx + lookforward_window)

        for i in range(start_idx, end_idx):
            c = candles[i]
            if swing.is_high:
                if c.high > swing.price:
                    # Check rejection back below
                    if c.body_top <= swing.price or (i + 1 < len(candles) and candles[i + 1].close < swing.price):
                        return i, c.high
            else:
                if c.low < swing.price:
                    # Check rejection back above
                    if c.body_bottom >= swing.price or (i + 1 < len(candles) and candles[i + 1].close > swing.price):
                        return i, c.low
        return None

    @staticmethod
    def check_displacement(candle: Candle, recent_candles: List[Candle], multiplier: float = 1.4) -> bool:
        """
        Verifies energetic displacement:
        - Candle body must be significantly larger than recent average candle bodies.
        - Candle body must comprise at least 60% of the candle's total range (strong momentum).
        """
        if not recent_candles:
            return True
        avg_body = sum(c.body_height for c in recent_candles) / len(recent_candles)
        if candle.body_height < avg_body * multiplier:
            return False
        if candle.total_range > 0 and (candle.body_height / candle.total_range) < 0.55:
            return False
        return True

    @classmethod
    def detect_market_structure_shift(
        cls,
        candles: List[Candle],
        swings: List[SwingPoint],
        sweep_index: int,
        search_window: int = 12,
        required_direction: Optional[Direction] = None
    ) -> Optional[Tuple[int, Direction, float]]:
        """
        Detects if an MSS occurred after a liquidity sweep.
        - For Bullish MSS: Price swept a low, then aggressively closes with full candle body
          above the recent internal swing high.
        - For Bearish MSS: Price swept a high, then aggressively closes with full candle body
          below the recent internal swing low.
        Returns: (mss_candle_index, Direction, broken_level) or None.
        """
        end_idx = min(len(candles), sweep_index + search_window)
        recent_candles = candles[max(0, sweep_index - 10):sweep_index]

        # Find the relevant internal swing point before/during the sweep
        relevant_swings = [s for s in swings if s.index < sweep_index]
        if not relevant_swings:
            return None

        for i in range(sweep_index + 1, end_idx):
            curr = candles[i]
            is_displaced = cls.check_displacement(curr, recent_candles)

            # Check Bullish MSS: Look for internal swing high to break
            if required_direction in (None, Direction.BULLISH):
                bullish_swings = [s for s in relevant_swings if s.is_high]
                if bullish_swings:
                    target_high = bullish_swings[-1]
                    if curr.close > target_high.price and is_displaced:
                        return i, Direction.BULLISH, target_high.price

            # Check Bearish MSS: Look for internal swing low to break
            if required_direction in (None, Direction.BEARISH):
                bearish_swings = [s for s in relevant_swings if not s.is_high]
                if bearish_swings:
                    target_low = bearish_swings[-1]
                    if curr.close < target_low.price and is_displaced:
                        return i, Direction.BEARISH, target_low.price

        return None
