"""
My Funded Futures (MFFU) Execution & Contract Specification Helper.
Translates institutional market signals directly into Tradovate / TradingView
micro-futures orders tailored specifically for a $50,000 evaluation account.
"""
from typing import Dict, Any
from src.core.models import Direction

MFFU_CONTRACTS = {
    "NQ": {
        "mffu_ticker": "MNQ",
        "name": "Micro E-mini Nasdaq-100",
        "full_ticker": "NQ",
        "tv_symbol": "CME_MINI:MNQ1!",
        "point_value_micro": 2.0,      # $2 per 1.00 index point
        "default_qty": 2,
    },
    "GOLD": {
        "mffu_ticker": "MGC",
        "name": "Micro Gold Futures",
        "full_ticker": "GC",
        "tv_symbol": "COMEX:MGC1!",
        "point_value_micro": 10.0,     # $10 per $1.00 move ($1 per 0.10 tick)
        "default_qty": 2,
    },
    "CRUDE": {
        "mffu_ticker": "MCL",
        "name": "Micro WTI Crude Oil",
        "full_ticker": "CL",
        "tv_symbol": "NYMEX:MCL1!",
        "point_value_micro": 100.0,    # $100 per $1.00 move ($1 per 0.01 tick)
        "default_qty": 2,
    },
    "BTC": {
        "mffu_ticker": "MBT",
        "name": "Micro Bitcoin Futures",
        "full_ticker": "BTC",
        "tv_symbol": "CME:MBT1!",
        "point_value_micro": 0.10,     # $0.10 per $1.00 move ($100 per $1,000 move)
        "default_qty": 2,
    },
    "ETH": {
        "mffu_ticker": "MET",
        "name": "Micro Ether Futures",
        "full_ticker": "ETH",
        "tv_symbol": "CME:MET1!",
        "point_value_micro": 0.10,     # $0.10 per $1.00 move (MET = 0.1 ETH)
        "default_qty": 2,
    },
    "SILVER": {
        "mffu_ticker": "SIL",
        "name": "Micro Silver Futures",
        "full_ticker": "SI",
        "tv_symbol": "COMEX:SIL1!",
        "point_value_micro": 1000.0,   # $1 per 0.001 ($1000 per $1.00 move)
        "default_qty": 2,
    },
    "SOL": {
        "mffu_ticker": "SOL/USDT",
        "name": "Solana Spot/Perp",
        "full_ticker": "SOL",
        "tv_symbol": "OKX:SOLUSDT",
        "point_value_micro": 1.0,
        "default_qty": 5,
    },
}


class MFFUHelper:
    @staticmethod
    def get_specs(symbol: str) -> Dict[str, Any]:
        clean = symbol.upper().replace("/", "").replace(":USDT", "USDT")
        if "NQ" in clean or "NASDAQ" in clean:
            return MFFU_CONTRACTS["NQ"]
        if "GOLD" in clean or "GC" in clean or "XAU" in clean:
            return MFFU_CONTRACTS["GOLD"]
        if "CRUDE" in clean or "CL" in clean or "OIL" in clean:
            return MFFU_CONTRACTS["CRUDE"]
        if "BTC" in clean:
            return MFFU_CONTRACTS["BTC"]
        if "ETH" in clean:
            return MFFU_CONTRACTS["ETH"]
        if "SILVER" in clean or "SI" in clean or "XAG" in clean:
            return MFFU_CONTRACTS["SILVER"]
        if "SOL" in clean:
            return MFFU_CONTRACTS["SOL"]
        return MFFU_CONTRACTS["NQ"]

    @classmethod
    def calculate_trade_metrics(
        cls,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: int = 2,
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
            "tv_url": f"https://www.tradingview.com/chart/?symbol={specs['tv_symbol']}",
            "quantity": quantity,
            "risk_points": risk_dist,
            "reward_points": reward_dist,
            "dollar_risk": dollar_risk,
            "dollar_profit": dollar_profit,
            "cushion_pct": cushion_pct,
        }
