"""
Universal market data fetcher: crypto (OKX/ccxt), commodities and US index
futures (Yahoo Finance). No private API keys required.

FIXED 2026-09-23:
  * RESPONSE CACHE. Previously this made ~11 Yahoo requests every 60 seconds
    (~15,800/day) from a single datacenter IP, with no key, no crumb, no
    backoff — and the same ticker was often fetched twice in one cycle
    (GOLD's SMT pull and SILVER's LTF pull are both SI=F). Yahoo rate-limits
    well below that, so the futures half of the universe was likely failing
    silently into "Error scanning GOLD".
  * Crude's SMT benchmark was Bitcoin. It now pairs with Brent (BZ=F).
  * is_stale() helper so callers can reject weekend/holiday data.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Optional
import urllib.request
import json
import time as _time
import requests
from src.core.models import Candle

try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False


# Cache TTLs. A 5m bar only closes every 5 minutes, so refetching it every
# 60 seconds buys nothing and costs four wasted requests.
CACHE_TTL_INTRADAY = 240      # seconds, for 5m data
CACHE_TTL_HOURLY = 900        # seconds, for 1h data
_CACHE: Dict[str, Tuple[float, List[Candle]]] = {}


FUTURES_COMMODITY_MAP = {
    # Metals
    "GOLD": "GC=F", "XAU/USD": "GC=F", "XAUUSD": "GC=F", "GC=F": "GC=F",
    "SILVER": "SI=F", "XAG/USD": "SI=F", "XAGUSD": "SI=F", "SI=F": "SI=F",
    # Energies
    "CRUDE": "CL=F", "CRUDE_OIL": "CL=F", "OIL": "CL=F", "WTI": "CL=F", "CL=F": "CL=F",
    "BRENT": "BZ=F", "BZ=F": "BZ=F",
    # US Index Futures
    "NQ": "NQ=F", "NQ1!": "NQ=F", "NQ=F": "NQ=F", "NQZ2026": "NQ=F",
    "NQZ26": "NQ=F", "NASDAQ": "NQ=F",
    "ES": "ES=F", "ES1!": "ES=F", "ES=F": "ES=F", "ESZ2026": "ES=F",
    "ESZ26": "ES=F", "SP500": "ES=F",
    "YM": "YM=F", "YM=F": "YM=F", "DOW": "YM=F",
}


def is_stale(candles: List[Candle], timeframe: str = "5m", max_bars_late: int = 6) -> bool:
    """
    True if the newest candle is too old to act on. Yahoo serves Friday's bars
    all weekend; without this the engine scans them as if live.
    """
    if not candles:
        return True
    minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}.get(timeframe, 5)
    age = datetime.now(timezone.utc) - candles[-1].timestamp
    return age > timedelta(minutes=minutes * max_bars_late)


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
        return clean in FUTURES_COMMODITY_MAP or clean.endswith("=F")

    @staticmethod
    def get_canonical_symbol(symbol: str) -> Tuple[str, bool]:
        clean = symbol.upper().strip()
        if clean in FUTURES_COMMODITY_MAP:
            return FUTURES_COMMODITY_MAP[clean], True
        return symbol, False

    @staticmethod
    def get_smt_benchmark_pair(symbol: str) -> str:
        clean = symbol.upper().strip()
        if clean in ("GOLD", "XAU/USD", "XAUUSD", "GC=F"):
            return "SI=F"
        if clean in ("SILVER", "XAG/USD", "XAGUSD", "SI=F"):
            return "GC=F"
        if clean in ("NQ", "NQZ2026", "NQZ26", "NQ1!", "NQ=F", "NASDAQ"):
            return "ES=F"
        if clean in ("ES", "ESZ2026", "ESZ26", "ES1!", "ES=F", "SP500"):
            return "NQ=F"
        # FIXED: crude used to fall through to BTC/USDT. WTI pairs with Brent.
        if clean in ("CRUDE", "CRUDE_OIL", "OIL", "WTI", "CL=F"):
            return "BZ=F"
        if clean in ("BRENT", "BZ=F"):
            return "CL=F"
        if clean in ("BTC/USDT", "BTC"):
            return "ETH/USDT"
        if clean in ("ETH/USDT", "ETH"):
            return "BTC/USDT"
        return "BTC/USDT"

    # ------------------------------------------------------------------
    @staticmethod
    def _cache_get(key: str, ttl: int) -> Optional[List[Candle]]:
        hit = _CACHE.get(key)
        if hit and (_time.time() - hit[0]) < ttl:
            return hit[1]
        return None

    @staticmethod
    def _cache_put(key: str, candles: List[Candle]) -> None:
        _CACHE[key] = (_time.time(), candles)

    # ------------------------------------------------------------------
    def fetch_commodity_candles(
        self, ticker: str, timeframe: str = "5m", limit: int = 100
    ) -> List[Candle]:
        interval = "5m" if timeframe in ("1m", "5m") else "1h" if timeframe in ("15m", "1h") else "1d"
        range_str = "5d" if interval == "5m" else "1mo" if interval == "1h" else "6mo"

        key = f"Y:{ticker}:{interval}"
        ttl = CACHE_TTL_INTRADAY if interval == "5m" else CACHE_TTL_HOURLY
        cached = self._cache_get(key, ttl)
        if cached is not None:
            return cached[-limit:]

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_str}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        res = data["chart"]["result"][0]
        timestamps = res["timestamp"]
        quote = res["indicators"]["quote"][0]
        candles: List[Candle] = []

        for i in range(len(timestamps)):
            o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
            v = quote["volume"][i] or 0.0
            if None in (o, h, l, c):
                continue
            ts = datetime.fromtimestamp(timestamps[i], tz=timezone.utc)
            candles.append(Candle(ts, float(o), float(h), float(l), float(c), float(v)))

        self._cache_put(key, candles)
        return candles[-limit:]

    def fetch_candles(
        self, symbol: str = "BTC/USDT", timeframe: str = "5m", limit: int = 100
    ) -> List[Candle]:
        canonical, is_comm = self.get_canonical_symbol(symbol)
        if is_comm:
            return self.fetch_commodity_candles(canonical, timeframe=timeframe, limit=limit)

        key = f"C:{symbol}:{timeframe}"
        ttl = CACHE_TTL_INTRADAY if timeframe in ("1m", "5m", "15m") else CACHE_TTL_HOURLY
        cached = self._cache_get(key, ttl)
        if cached is not None and len(cached) >= limit:
            return cached[-limit:]

        for ex in self.exchanges:
            try:
                ohlcv = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
                candles: List[Candle] = []
                for row in ohlcv:
                    ts = datetime.fromtimestamp(row[0] / 1000.0, tz=timezone.utc)
                    candles.append(Candle(
                        timestamp=ts, open=float(row[1]), high=float(row[2]),
                        low=float(row[3]), close=float(row[4]), volume=float(row[5]),
                    ))
                if candles:
                    self._cache_put(key, candles)
                    return candles
            except Exception:
                continue

        inst_id = symbol.replace("/", "-")
        bar_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}
        bar = bar_map.get(timeframe, "5m")
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={min(limit, 300)}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        candles = []
        for row in reversed(data):
            ts = datetime.fromtimestamp(int(row[0]) / 1000.0, tz=timezone.utc)
            candles.append(Candle(
                timestamp=ts, open=float(row[1]), high=float(row[2]),
                low=float(row[3]), close=float(row[4]), volume=float(row[5]),
            ))
        if candles:
            self._cache_put(key, candles)
        return candles


CryptoDataFetcher = MarketDataFetcher
