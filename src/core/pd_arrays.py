"""
ICT PD Array Matrix:
- Fair Value Gaps (FVG) and Consequent Encroachment (CE: 50% midpoint)
- Order Blocks (OB) and Mean Threshold (MT: 50% candle body midpoint)
- Breaker Blocks
- Dealing Range Premium vs. Discount Equilibrium (50%)
"""
from typing import List, Optional
from src.core.models import Candle, FairValueGap, OrderBlock, BreakerBlock, Direction


class PDArrayEngine:
    @staticmethod
    def calculate_equilibrium(high: float, low: float) -> float:
        """
        Computes 50% Equilibrium of the dealing range.
        Price < 50% is Discount (only longs allowed).
        Price > 50% is Premium (only shorts allowed).
        """
        return low + (high - low) * 0.5

    @staticmethod
    def is_in_discount(price: float, range_high: float, range_low: float) -> bool:
        eq = range_low + (range_high - range_low) * 0.5
        return price <= eq

    @staticmethod
    def is_in_premium(price: float, range_high: float, range_low: float) -> bool:
        eq = range_low + (range_high - range_low) * 0.5
        return price >= eq

    @staticmethod
    def find_fair_value_gaps(
        candles: List[Candle], min_gap_percent: float = 0.05
    ) -> List[FairValueGap]:
        """
        Scans for 3-candle Fair Value Gaps (FVGs).
        - Bullish FVG: Candle 1 High < Candle 3 Low
        - Bearish FVG: Candle 1 Low > Candle 3 High
        """
        fvgs: List[FairValueGap] = []
        n = len(candles)

        for i in range(2, n):
            c1 = candles[i - 2]
            c2 = candles[i - 1]
            c3 = candles[i]

            # Bullish FVG
            if c3.low > c1.high:
                gap_size = c3.low - c1.high
                gap_pct = (gap_size / c1.high) * 100
                if gap_pct >= min_gap_percent:
                    ce = c1.high + (gap_size * 0.5)
                    fvgs.append(
                        FairValueGap(
                            top=c3.low,
                            bottom=c1.high,
                            consequent_encroachment=ce,
                            direction=Direction.BULLISH,
                            candle_index=i - 1,
                            timestamp=c2.timestamp,
                        )
                    )

            # Bearish FVG
            elif c1.low > c3.high:
                gap_size = c1.low - c3.high
                gap_pct = (gap_size / c1.low) * 100
                if gap_pct >= min_gap_percent:
                    ce = c3.high + (gap_size * 0.5)
                    fvgs.append(
                        FairValueGap(
                            top=c1.low,
                            bottom=c3.high,
                            consequent_encroachment=ce,
                            direction=Direction.BEARISH,
                            candle_index=i - 1,
                            timestamp=c2.timestamp,
                        )
                    )

        return fvgs

    @staticmethod
    def find_order_block(
        candles: List[Candle],
        displacement_index: int,
        direction: Direction
    ) -> Optional[OrderBlock]:
        """
        Locates the qualified Order Block immediately prior to displacement:
        - Bullish OB: The lowest down-close candle prior to upward displacement.
        - Bearish OB: The highest up-close candle prior to downward displacement.
        """
        start = max(0, displacement_index - 5)
        candidates = candles[start:displacement_index]

        if direction == Direction.BULLISH:
            down_candles = [c for c in candidates if c.is_bearish]
            if not down_candles:
                return None
            ob_candle = min(down_candles, key=lambda c: c.low)
            mt = ob_candle.body_bottom + (ob_candle.body_height * 0.5)
            idx = candles.index(ob_candle)
            return OrderBlock(
                high=ob_candle.high,
                low=ob_candle.low,
                mean_threshold=mt,
                direction=Direction.BULLISH,
                candle_index=idx,
                timestamp=ob_candle.timestamp,
            )
        else:
            up_candles = [c for c in candidates if c.is_bullish]
            if not up_candles:
                return None
            ob_candle = max(up_candles, key=lambda c: c.high)
            mt = ob_candle.body_bottom + (ob_candle.body_height * 0.5)
            idx = candles.index(ob_candle)
            return OrderBlock(
                high=ob_candle.high,
                low=ob_candle.low,
                mean_threshold=mt,
                direction=Direction.BEARISH,
                candle_index=idx,
                timestamp=ob_candle.timestamp,
            )
