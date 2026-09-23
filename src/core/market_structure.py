"""
Institutional Market Structure:
- 3-bar Short-Term Highs (STH) and Lows (STL)
- Liquidity Sweeps (Wick only: "Wicks do the damage")
- Market Structure Shifts (MSS) (Full body closures: "Bodies tell the story")
- Displacement Candle Validation

FIXED 2026-09-23:
  * detect_market_structure_shift() now accepts required_direction. Previously it
    returned whichever MSS it found FIRST in the search window, in either
    direction. After sweeping a low and waiting for a bullish MSS, one
    counter-direction displaced candle anywhere in the next 12 bars returned
    BEARISH and the caller discarded the setup — never seeing the bullish MSS
    that formed two bars later.
"""
from typing import List, Tuple, Optional
from src.core.models import Candle, SwingPoint, Direction


class MarketStructureAnalyzer:
    @staticmethod
    def find_swing_points(candles: List[Candle], left_bars: int = 2, right_bars: int = 2) -> List[SwingPoint]:
        """
        Identifies valid swing points using 3-to-5 bar fractal formation.

        NOTE: uses strict inequality, so a RELATIVE EQUAL HIGH can never be a
        swing point. Episodes 20/29/30 treat equal highs as the primary draw on
        liquidity. Left as-is deliberately — changing it alters signal volume
        significantly and should be a conscious decision, not a silent patch.
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
        Returns (candle_index, sweep_extreme_price) if swept, else None.
        """
        start_idx = swing.index + 1
        end_idx = min(len(candles), start_idx + lookforward_window)

        for i in range(start_idx, end_idx):
            c = candles[i]
            if swing.is_high:
                if c.high > swing.price:
                    if c.body_top <= swing.price or (i + 1 < len(candles) and candles[i + 1].close < swing.price):
                        return i, c.high
            else:
                if c.low < swing.price:
                    if c.body_bottom >= swing.price or (i + 1 < len(candles) and candles[i + 1].close > swing.price):
                        return i, c.low
        return None

    @staticmethod
    def check_displacement(candle: Candle, recent_candles: List[Candle], multiplier: float = 1.4) -> bool:
        """
        Verifies energetic displacement:
        - Body must be >= multiplier x the recent average body height.
        - Body must be at least 55% of the candle's total range.

        NOTE: multiplier is a fixed constant, never calibrated to instrument or
        volatility. 1.4x on MNQ and 1.4x on MGC mean very different things.
        """
        if not recent_candles:
            return False  # FIXED: was `return True` — failed OPEN, treating every
                          # candle as displaced when the lookback window was empty.
        avg_body = sum(c.body_height for c in recent_candles) / len(recent_candles)
        if avg_body <= 0:
            return False
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
        required_direction: Optional[Direction] = None,
    ) -> Optional[Tuple[int, Direction, float]]:
        """
        Detects an MSS after a liquidity sweep.

        required_direction:
            Direction.BULLISH -> only look for a close above the prior swing high
            Direction.BEARISH -> only look for a close below the prior swing low
            None              -> legacy behaviour (first match either way)

        Pass the direction you actually want. Leaving it None reintroduces the
        premature-termination bug this parameter exists to fix.
        """
        end_idx = min(len(candles), sweep_index + search_window)
        recent_candles = candles[max(0, sweep_index - 10):sweep_index]

        relevant_swings = [s for s in swings if s.index < sweep_index]
        if not relevant_swings:
            return None

        bullish_swings = [s for s in relevant_swings if s.is_high]
        bearish_swings = [s for s in relevant_swings if not s.is_high]

        for i in range(sweep_index + 1, end_idx):
            curr = candles[i]
            is_displaced = cls.check_displacement(curr, recent_candles)
            if not is_displaced:
                continue

            if required_direction in (None, Direction.BULLISH) and bullish_swings:
                target_high = bullish_swings[-1]
                if curr.close > target_high.price:
                    return i, Direction.BULLISH, target_high.price

            if required_direction in (None, Direction.BEARISH) and bearish_swings:
                target_low = bearish_swings[-1]
                if curr.close < target_low.price:
                    return i, Direction.BEARISH, target_low.price

        return None
