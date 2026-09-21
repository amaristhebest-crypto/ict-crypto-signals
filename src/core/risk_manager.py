"""
Risk and Trade Management according to ICT Core Content (Month 2 & Reference Guide).
- 1-1.5% fixed equity risk
- 50% Drawdown reduction rule on losing streaks
- OTE (Optimal Trade Entry) Fibonacci calculations (61.8%, 70.5%, 79.0%)
- Target scaling (-0.27, -0.62, -1.00 expansions)
"""
from typing import Dict, Tuple
from src.core.models import Direction


class ICTRiskManager:
    def __init__(self, initial_risk_percent: float = 1.0):
        self.base_risk_pct = initial_risk_percent
        self.current_risk_pct = initial_risk_percent
        self.consecutive_losses = 0
        self.consecutive_wins = 0

    def record_trade_result(self, is_win: bool):
        """
        Implements Huddleston's Drawdown Mitigation Rule:
        - If 2 consecutive losses occur, reduce risk by 50%.
        - Do not increase back to standard risk until 2 consecutive wins are logged.
        """
        if is_win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            if self.consecutive_wins >= 2 and self.current_risk_pct < self.base_risk_pct:
                self.current_risk_pct = min(self.base_risk_pct, self.current_risk_pct * 2.0)
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            if self.consecutive_losses >= 2:
                self.current_risk_pct = max(0.25, self.current_risk_pct * 0.5)

    @staticmethod
    def calculate_ote_levels(
        swing_low: float, swing_high: float, direction: Direction
    ) -> Dict[str, float]:
        """
        Calculates ICT Optimal Trade Entry (OTE) levels:
        - 50.0% Equilibrium
        - 61.8% Retracement
        - 70.5% OTE Sweet Spot
        - 79.0% Deep Retracement
        - -0.27 Extension (Target 1 / Symmetrical)
        - -0.62 Extension (Target 2 / Macro Expansion)
        - -1.00 Extension (Target 3 / Full Delivery)
        """
        diff = swing_high - swing_low
        if direction == Direction.BULLISH:
            return {
                "equilibrium": swing_high - (diff * 0.50),
                "retrace_618": swing_high - (diff * 0.618),
                "ote_705": swing_high - (diff * 0.705),
                "retrace_790": swing_high - (diff * 0.790),
                "ext_027": swing_high + (diff * 0.272),
                "ext_062": swing_high + (diff * 0.618),
                "ext_100": swing_high + (diff * 1.000),
            }
        else:
            return {
                "equilibrium": swing_low + (diff * 0.50),
                "retrace_618": swing_low + (diff * 0.618),
                "ote_705": swing_low + (diff * 0.705),
                "retrace_790": swing_low + (diff * 0.790),
                "ext_027": swing_low - (diff * 0.272),
                "ext_062": swing_low - (diff * 0.618),
                "ext_100": swing_low - (diff * 1.000),
            }

    @staticmethod
    def calculate_position_size(
        account_equity: float, risk_percent: float, entry_price: float, stop_loss: float
    ) -> Tuple[float, float]:
        """
        Returns: (position_size_in_units, risk_amount_dollars)
        """
        risk_amount = account_equity * (risk_percent / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return 0.0, 0.0
        position_size = risk_amount / risk_per_unit
        return position_size, risk_amount
