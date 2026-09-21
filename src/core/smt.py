"""
ICT Smart Money Tool (SMT) Divergence:
Compares correlated assets (BTC vs ETH) to detect cracks in correlation.
"""
from typing import List
from src.core.models import Candle, SMTResult, Direction
from src.core.market_structure import MarketStructureAnalyzer


class SMTDivergenceDetector:
    @classmethod
    def analyze(
        cls,
        asset_a_candles: List[Candle],
        asset_b_candles: List[Candle],
        asset_a_name: str = "BTC/USDT",
        asset_b_name: str = "ETH/USDT",
        lookback: int = 25
    ) -> SMTResult:
        """
        Analyzes recent swing highs and lows across both assets.
        Checks for cracks in correlation at key turning points.
        """
        if len(asset_a_candles) < 10 or len(asset_b_candles) < 10:
            return SMTResult(detected=False)

        a_recent = asset_a_candles[-lookback:]
        b_recent = asset_b_candles[-lookback:]

        a_swings = MarketStructureAnalyzer.find_swing_points(a_recent, left_bars=2, right_bars=2)
        b_swings = MarketStructureAnalyzer.find_swing_points(b_recent, left_bars=2, right_bars=2)

        a_lows = [s for s in a_swings if not s.is_high]
        b_lows = [s for s in b_swings if not s.is_high]

        # Check Bullish SMT: Asset A prints Lower Low while Asset B prints Higher Low
        if len(a_lows) >= 2 and len(b_lows) >= 2:
            a_prev_low, a_last_low = a_lows[-2], a_lows[-1]
            b_prev_low, b_last_low = b_lows[-2], b_lows[-1]

            # Asset A made a Lower Low
            a_is_lower_low = a_last_low.price < a_prev_low.price
            # Asset B made a Higher Low (refused to sweep)
            b_is_higher_low = b_last_low.price > b_prev_low.price

            if a_is_lower_low and b_is_higher_low:
                return SMTResult(
                    detected=True,
                    direction=Direction.BULLISH,
                    asset_a=asset_a_name,
                    asset_a_sweep=f"Lower Low ({a_last_low.price:.2f} < {a_prev_low.price:.2f})",
                    asset_b=asset_b_name,
                    asset_b_sweep=f"Higher Low ({b_last_low.price:.2f} > {b_prev_low.price:.2f})",
                    timestamp=a_last_low.timestamp,
                    description=(
                        f"Bullish SMT Divergence: {asset_a_name} swept liquidity with a Lower Low, "
                        f"while {asset_b_name} formed a Higher Low (Institutional Absorption)."
                    ),
                )

        # Check Bearish SMT: Asset A prints Higher High while Asset B prints Lower High
        a_highs = [s for s in a_swings if s.is_high]
        b_highs = [s for s in b_swings if s.is_high]

        if len(a_highs) >= 2 and len(b_highs) >= 2:
            a_prev_high, a_last_high = a_highs[-2], a_highs[-1]
            b_prev_high, b_last_high = b_highs[-2], b_highs[-1]

            a_is_higher_high = a_last_high.price > a_prev_high.price
            b_is_lower_high = b_last_high.price < b_prev_high.price

            if a_is_higher_high and b_is_lower_high:
                return SMTResult(
                    detected=True,
                    direction=Direction.BEARISH,
                    asset_a=asset_a_name,
                    asset_a_sweep=f"Higher High ({a_last_high.price:.2f} > {a_prev_high.price:.2f})",
                    asset_b=asset_b_name,
                    asset_b_sweep=f"Lower High ({b_last_high.price:.2f} < {b_prev_high.price:.2f})",
                    timestamp=a_last_high.timestamp,
                    description=(
                        f"Bearish SMT Divergence: {asset_a_name} swept Buy-Side Liquidity with a Higher High, "
                        f"while {asset_b_name} formed a Lower High (Institutional Distribution)."
                    ),
                )

        return SMTResult(detected=False)
