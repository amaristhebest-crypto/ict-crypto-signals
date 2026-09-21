"""
Cryptocurrency market data fetcher via public REST APIs (no private API keys required).
Uses ccxt with automatic fallback to Binance public REST endpoints.
"""
from datetime import datetime, timezone
from typing import List
import requests
from src.core.models import Candle

try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False


class CryptoDataFetcher:
    def __init__(self, exchange_id: str = "okx"):
        self.exchange_id = exchange_id
        self.exchanges = []
        if HAS_CCXT:
            for ex_name in [exchange_id, "okx", "gateio", "kraken"]:
                try:
                    ex_class = getattr(ccxt, ex_name)
                    self.exchanges.append(ex_class({"enableRateLimit": True}))
                except Exception:
                    pass

    def fetch_candles(
        self, symbol: str = "BTC/USDT", timeframe: str = "5m", limit: int = 100
    ) -> List[Candle]:
        """
        Fetches OHLCV candles with multi-exchange fallback.
        """
        for ex in self.exchanges:
            try:
                ohlcv = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
                candles: List[Candle] = []
                for row in ohlcv:
                    ts = datetime.fromtimestamp(row[0] / 1000.0, tz=timezone.utc)
                    candles.append(
                        Candle(
                            timestamp=ts,
                            open=float(row[1]),
                            high=float(row[2]),
                            low=float(row[3]),
                            close=float(row[4]),
                            volume=float(row[5]),
                        )
                    )
                return candles
            except Exception:
                continue

        # Direct OKX public REST API fallback
        inst_id = symbol.replace("/", "-")
        bar_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}
        bar = bar_map.get(timeframe, "5m")
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        # OKX returns reverse chronological order, reverse to chronological
        candles = []
        for row in reversed(data):
            ts = datetime.fromtimestamp(int(row[0]) / 1000.0, tz=timezone.utc)
            candles.append(
                Candle(
                    timestamp=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        return candles
