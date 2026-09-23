"""
Session and Kill Zone tracking based on New York Time (EST/EDT).
"""
from datetime import datetime, time
import zoneinfo

NY_TZ = zoneinfo.ZoneInfo("America/New_York")
UTC_TZ = zoneinfo.ZoneInfo("UTC")
IST_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")


class SessionDetector:
    """
    Identifies active ICT Kill Zones and session benchmarks.
    Displays both NY Time and Indian Standard Time (IST - UTC+5:30).
    """

    @staticmethod
    def to_ny_time(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC_TZ)
        return dt.astimezone(NY_TZ)

    @staticmethod
    def to_ist_time(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC_TZ)
        return dt.astimezone(IST_TZ)

    @classmethod
    def get_active_session(cls, dt: datetime) -> str:
        ny = cls.to_ny_time(dt)
        t = ny.time()

        # New York Lunch Dead Zone: 12:00 PM - 1:00 PM EST (09:30 PM - 10:30 PM IST)
        if time(12, 0) <= t < time(13, 0):
            return "NY Lunch Dead Zone (12:00-13:00 EST / 09:30 PM-10:30 PM IST - DO NOT TRADE)"

        # New York Afternoon Session: 13:30 - 16:00 EST (11:00 PM - 01:30 AM IST)
        if time(13, 30) <= t < time(16, 0):
            if time(14, 0) <= t < time(15, 0):
                return "ICT Silver Bullet PM (14:00-15:00 EST / 11:30 PM-12:30 AM IST)"
            return "New York PM Session (13:30-16:00 EST / 11:00 PM-01:30 AM IST)"

        # Silver Bullet AM Window: 10:00 - 11:00 EST (07:30 PM - 08:30 PM IST)
        if time(10, 0) <= t < time(11, 0):
            return "ICT Silver Bullet AM (10:00-11:00 EST / 07:30 PM-08:30 PM IST)"

        # New York Open Kill Zone: 07:00 - 10:00 EST (04:30 PM - 07:30 PM IST)
        if time(7, 0) <= t < time(10, 0):
            if time(9, 30) <= t < time(9, 45):
                return "New York Open (NYSE Bell 09:30 EST / 07:00 PM IST)"
            if time(8, 30) <= t < time(10, 0):
                return "NY Morning Hunt Window (08:30-10:00 EST / 06:00 PM-07:30 PM IST)"
            return "New York Open Kill Zone (07:00-10:00 EST / 04:30 PM-07:30 PM IST)"

        # London Close Kill Zone: 10:00 - 12:00 EST (07:30 PM - 09:30 PM IST)
        if time(10, 0) <= t < time(12, 0):
            return "London Close Kill Zone (10:00-12:00 EST / 07:30 PM-09:30 PM IST)"

        # London Open Kill Zone: 02:00 - 05:00 EST (11:30 AM - 02:30 PM IST)
        if time(2, 0) <= t < time(5, 0):
            return "London Open Kill Zone (02:00-05:00 EST / 11:30 AM-02:30 PM IST)"

        # Asian Range: 20:00 - 00:00 EST (05:30 AM - 09:30 AM IST)
        if time(20, 0) <= t or t < time(0, 0):
            return "Asian Range (20:00-00:00 EST / 05:30 AM-09:30 AM IST)"

        # Central Bank Dealers Range (CBDR): 14:00 - 20:00 EST (11:30 PM - 05:30 AM IST)
        if time(14, 0) <= t < time(20, 0):
            return "CBDR Range (14:00-20:00 EST / 11:30 PM-05:30 AM IST)"

        return "Out-of-Killzone / Interbank Consolidation"

    @classmethod
    def is_killzone_active(cls, dt: datetime) -> bool:
        session = cls.get_active_session(dt)
        if "DO NOT TRADE" in session or "Dead Zone" in session:
            return False
        return any(
            kz in session
            for kz in [
                "London Open",
                "New York Open",
                "Morning Hunt",
                "New York PM",
                "London Close",
                "Silver Bullet",
                "Asian Range",
            ]
        )

    @classmethod
    def get_ny_midnight_open(cls, candles: list) -> float:
        """
        Locates the 00:00 NY Midnight Open price from a candle sequence.
        """
        for c in reversed(candles):
            ny_dt = cls.to_ny_time(c.timestamp)
            if ny_dt.hour == 0 and ny_dt.minute == 0:
                return c.open
        # Fallback to the candle closest to midnight
        for c in reversed(candles):
            ny_dt = cls.to_ny_time(c.timestamp)
            if ny_dt.hour == 0:
                return c.open
        return candles[0].open

    @classmethod
    def get_session_liquidity_map(cls, candles: list) -> dict:
        """
        Builds the institutional Session Liquidity Map:
        - NY Midnight Open (00:00 ET) dealing benchmark
        - Asian Range (19:00 - 02:00 ET): High & Low, tracking if swept
        - London Range (02:00 - 05:00 ET): High & Low, tracking if swept
        - Current Dealing Bias (Discount vs Premium relative to Midnight Open)
        """
        if not candles:
            return {}
        latest_ny = cls.to_ny_time(candles[-1].timestamp)
        today_date = latest_ny.date()

        midnight_open = None
        asian_candles = []
        london_candles = []
        after_asia_candles = []
        after_london_candles = []

        for c in candles:
            ny = cls.to_ny_time(c.timestamp)
            # Asian range: evening before (date = today - 1 and hour >= 19) OR (date = today and hour < 2)
            if (ny.date() == today_date and ny.hour < 2) or (ny.date() < today_date and ny.hour >= 19):
                asian_candles.append(c)
            elif ny.date() == today_date and ny.hour >= 2:
                after_asia_candles.append(c)

            # Midnight Open: today at hour 0
            if ny.date() == today_date and ny.hour == 0 and midnight_open is None:
                midnight_open = c.open

            # London range: today between 02:00 and 05:00
            if ny.date() == today_date and 2 <= ny.hour < 5:
                london_candles.append(c)
            elif ny.date() == today_date and ny.hour >= 5:
                after_london_candles.append(c)

        asian_hi = max(c.high for c in asian_candles) if asian_candles else None
        asian_lo = min(c.low for c in asian_candles) if asian_candles else None
        london_hi = max(c.high for c in london_candles) if london_candles else None
        london_lo = min(c.low for c in london_candles) if london_candles else None

        # Detect sweeps
        asian_hi_swept = any(c.high > asian_hi for c in after_asia_candles) if (asian_hi and after_asia_candles) else False
        asian_lo_swept = any(c.low < asian_lo for c in after_asia_candles) if (asian_lo and after_asia_candles) else False
        london_hi_swept = any(c.high > london_hi for c in after_london_candles) if (london_hi and after_london_candles) else False
        london_lo_swept = any(c.low < london_lo for c in after_london_candles) if (london_lo and after_london_candles) else False

        current_px = candles[-1].close
        bias = "NEUTRAL"
        if midnight_open:
            bias = "DISCOUNT (Bullish Hunting Zone)" if current_px < midnight_open else "PREMIUM (Bearish Hunting Zone)"

        return {
            "current_price": current_px,
            "midnight_open": midnight_open,
            "bias": bias,
            "asian_high": asian_hi,
            "asian_low": asian_lo,
            "asian_hi_swept": asian_hi_swept,
            "asian_lo_swept": asian_lo_swept,
            "london_high": london_hi,
            "london_low": london_lo,
            "london_hi_swept": london_hi_swept,
            "london_lo_swept": london_lo_swept,
        }

