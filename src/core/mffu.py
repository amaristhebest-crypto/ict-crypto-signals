"""
My Funded Futures (MFFU) execution & contract specification helper.
Translates an ICT signal into a Tradovate / TradingView micro-futures order.

FIXED 2026-09-23:
  * SOL was listed as an MFFU contract with ticker "SOL/USDT" and a placeholder
    point value of 1.0. There is no Micro Solana futures contract on any
    exchange. The dashboard was printing a bracket order for an instrument
    that cannot be traded. Now flagged tradeable=False and the alert layer
    shows a warning instead of an order.
  * MET point value 0.50 -> 0.10 (MET is 0.1 ETH, so $1 of ETH = $0.10).
  * get_specs() no longer silently falls back to NQ for unknown symbols.
  * cushion_pct is still measured against a hardcoded $2,000. That number is
    the TOTAL account drawdown and it TRAILS end-of-day, so the figure shown is
    not the cushion you actually have. Kept for continuity; do not rely on it.
"""
from typing import Dict, Any

MFFU_CONTRACTS = {
    "NQ": {
        "mffu_ticker": "MNQ", "name": "Micro E-mini Nasdaq-100", "full_ticker": "NQ",
        "tv_symbol": "CME_MINI:MNQ1!", "point_value_micro": 2.0,      # $2 per index point
        "default_qty": 2, "tradeable": True,
    },
    "GOLD": {
        "mffu_ticker": "MGC", "name": "Micro Gold Futures", "full_ticker": "GC",
        "tv_symbol": "COMEX:MGC1!", "point_value_micro": 10.0,        # 10 troy oz
        "default_qty": 2, "tradeable": True,
    },
    "CRUDE": {
        "mffu_ticker": "MCL", "name": "Micro WTI Crude Oil", "full_ticker": "CL",
        "tv_symbol": "NYMEX:MCL1!", "point_value_micro": 100.0,       # 100 barrels
        "default_qty": 2, "tradeable": True,
    },
    "SILVER": {
        "mffu_ticker": "SIL", "name": "Micro Silver Futures", "full_ticker": "SI",
        "tv_symbol": "COMEX:SIL1!", "point_value_micro": 1000.0,      # 1,000 troy oz
        "default_qty": 1, "tradeable": True,
    },
    "BTC": {
        "mffu_ticker": "MBT", "name": "Micro Bitcoin Futures", "full_ticker": "BTC",
        "tv_symbol": "CME:MBT1!", "point_value_micro": 0.10,          # 0.1 BTC
        "default_qty": 2, "tradeable": True,
    },
    "ETH": {
        "mffu_ticker": "MET", "name": "Micro Ether Futures", "full_ticker": "ETH",
        "tv_symbol": "CME:MET1!", "point_value_micro": 0.10,          # 0.1 ETH
        "default_qty": 2, "tradeable": True,
    },
    "SOL": {
        "mffu_ticker": "SOL/USDT", "name": "Solana (spot/perp - NOT a futures contract)",
        "full_ticker": "SOL", "tv_symbol": "OKX:SOLUSDT", "point_value_micro": 1.0,
        "default_qty": 0, "tradeable": False,
    },
}

_UNKNOWN = {
    "mffu_ticker": "UNKNOWN", "name": "Unmapped instrument", "full_ticker": "?",
    "tv_symbol": "", "point_value_micro": 0.0, "default_qty": 0, "tradeable": False,
}


class MFFUHelper:
    @staticmethod
    def get_specs(symbol: str) -> Dict[str, Any]:
        clean = symbol.upper().replace("/", "")
        # Order matters: check the most specific tokens first.
        if "NQ" in clean or "NASDAQ" in clean:
            return MFFU_CONTRACTS["NQ"]
        if "GOLD" in clean or "XAU" in clean or clean.startswith("GC"):
            return MFFU_CONTRACTS["GOLD"]
        if "SILVER" in clean or "XAG" in clean or clean.startswith("SI"):
            return MFFU_CONTRACTS["SILVER"]
        if "CRUDE" in clean or "OIL" in clean or "WTI" in clean or clean.startswith("CL"):
            return MFFU_CONTRACTS["CRUDE"]
        if "BTC" in clean:
            return MFFU_CONTRACTS["BTC"]
        if "ETH" in clean:
            return MFFU_CONTRACTS["ETH"]
        if "SOL" in clean:
            return MFFU_CONTRACTS["SOL"]
        # FIXED: was `return MFFU_CONTRACTS["NQ"]`. An unmapped symbol silently
        # got Nasdaq dollar math at $2/point with no warning anywhere.
        return _UNKNOWN

    @classmethod
    def calculate_trade_metrics(
        cls, symbol: str, entry_price: float, stop_loss: float,
        take_profit: float, quantity: int = 2,
    ) -> Dict[str, Any]:
        specs = cls.get_specs(symbol)
        pt_val = specs["point_value_micro"]
        risk_dist = abs(entry_price - stop_loss)
        reward_dist = abs(take_profit - entry_price)

        dollar_risk = risk_dist * pt_val * quantity
        dollar_profit = reward_dist * pt_val * quantity
        cushion_pct = (dollar_risk / 2000.0) * 100.0 if dollar_risk > 0 else 0.0

        return {
            "mffu_ticker": specs["mffu_ticker"],
            "contract_name": specs["name"],
            "tv_symbol": specs["tv_symbol"],
            "tv_url": (f"https://www.tradingview.com/chart/?symbol={specs['tv_symbol']}"
                       if specs["tv_symbol"] else ""),
            "tradeable": specs["tradeable"],
            "quantity": quantity,
            "risk_points": risk_dist,
            "reward_points": reward_dist,
            "dollar_risk": dollar_risk,
            "dollar_profit": dollar_profit,
            "cushion_pct": cushion_pct,
        }
