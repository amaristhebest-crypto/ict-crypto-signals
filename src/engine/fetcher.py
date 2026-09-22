"""
Universal market data fetcher supporting both Cryptocurrency (OKX/Binance)
and Global Commodities (Gold, Silver, Crude Oil) without requiring private API keys.
"""
from datetime import datetime, timezone
from typing import List, Tuple
import urllib.request
import json
import requests
from src.core.models import Candle

try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False

COMMODITY_MAP = {
    "GOLD": "GC=F",
    "XAU/USD": "GC=F",
    "XAUUSD": "GC=F",
    "GC=F": "GC=F",
    "SILVER": "SI=F",
    "XAG/USD": "SI=F",
    "XAGUSD": "SI=F",
    "SI=F": "SI=F",
    "CRUDE": "CL=F",
    "CRUDE_OIL": "CL=F",
    "OIL": "CL=F",
    "WTI": "CL=F",
    "CL=F": "CL=F",
    "BRENT": "BZ=F",
    "BZ=F": "BZ=F",
}


class MarketDataFetcher:
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

    @staticmethod
    def is_commodity(symbol: str) -> bool:
        clean = symbol.upper().strip()
        return clean in COMMODITY_MAP or clean.endswith("=F")

    @staticmethod
    def get_canonical_symbol(symbol: str) -> Tuple[str, bool]:
        clean = symbol.upper().strip()
        if clean in COMMODITY_MAP:
            return COMMODITY_MAP[clean], True
        return symbol, False

    @staticmethod
    def get_smt_benchmark_pair(symbol: str) -> str:
        clean = symbol.upper().strip()
        if clean in ("GOLD", "XAU/USD", "XAUUSD", "GC=F"):
            return "SI=F"  # Gold benchmark is Silver
        if clean in ("SILVER", "XAG/USD", "XAGUSD", "SI=F"):
            return "GC=F"  # Silver benchmark is Gold
        if clean in ("BTC/USDT", "BTC"):
            return "ETH/USDT"
        return "BTC/USDT"

    def fetch_commodity_candles(
        self, ticker: str, timeframe: str = "5m", limit: int = 100
    ) -> List[Candle]:
        """
        Fetches live commodity futures (Gold GC=F, Silver SI=F, Crude CL=F).
        """
        interval = "5m" if timeframe in ("1m", "5m") else "1h" if timeframe in ("15m", "1h") else "1d"
        range_str = "5d" if interval == "5m" else "1mo" if interval == "1h" else "6mo"

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_str}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        res = data["chart"]["result"][0]
        timestamps = res["timestamp"]
        quote = res["indicators"]["quote"][0]
        candles: List[Candle] = []

        for i in range(len(timestamps)):
            o = quote["open"][i]
            h = quote["high"][i]
            l = quote["low"][i]
            c = quote["close"][i]
            v = quote["volume"][i] or 0.0
            if None in (o, h, l, c):
                continue
            ts = datetime.fromtimestamp(timestamps[i], tz=timezone.utc)
            candles.append(Candle(ts, float(o), float(h), float(l), float(c), float(v)))

        return candles[-limit:]

    def fetch_candles(
        self, symbol: str = "BTC/USDT", timeframe: str = "5m", limit: int = 100
    ) -> List[Candle]:
        """
        Universal entry point: routes commodities to commodity engine and crypto to exchange engine.
        """
        canonical, is_comm = self.get_canonical_symbol(symbol)
        if is_comm:
            return self.fetch_commodity_candles(canonical, timeframe=timeframe, limit=limit)

        # Route to Crypto Exchanges
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


# Backwards compatibility alias
CryptoDataFetcher = MarketDataFetcher
