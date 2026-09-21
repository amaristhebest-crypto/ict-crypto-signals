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
    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        if HAS_CCXT:
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class({"enableRateLimit": True})
        else:
            self.exchange = None

    def fetch_candles(
        self, symbol: str = "BTC/USDT", timeframe: str = "5m", limit: int = 100
    ) -> List[Candle]:
        """
        Fetches OHLCV candles and parses them into typed Candle models.
        """
        if self.exchange:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
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
            except Exception as e:
                # Fallback to direct HTTP endpoint
                pass

        # Direct Binance public REST fallback
        clean_symbol = symbol.replace("/", "").replace(":USDT", "")
        url = f"https://api.binance.com/api/v3/klines?symbol={clean_symbol}&interval={timeframe}&limit={limit}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        candles = []
        for row in data:
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
