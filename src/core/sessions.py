"""
Session and Kill Zone tracking based on New York Time (EST/EDT).
"""
from datetime import datetime, time
import zoneinfo

NY_TZ = zoneinfo.ZoneInfo("America/New_York")
UTC_TZ = zoneinfo.ZoneInfo("UTC")


class SessionDetector:
    """
    Identifies active ICT Kill Zones and session benchmarks.
    All logic strictly maps to NY Time as mandated by Michael Huddleston.
    """

    @staticmethod
    def to_ny_time(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC_TZ)
        return dt.astimezone(NY_TZ)

    @classmethod
    def get_active_session(cls, dt: datetime) -> str:
        ny = cls.to_ny_time(dt)
        t = ny.time()

        # New York Lunch Dead Zone: 12:00 PM - 1:00 PM EST (Hard No-Trade Zone per Ep 5 & 39)
        if time(12, 0) <= t < time(13, 0):
            return "New York Lunch Dead Zone (12:00-13:00 EST - DO NOT TRADE)"

        # New York Afternoon Session: 13:30 - 16:00 EST (Ep 41)
        if time(13, 30) <= t < time(16, 0):
            if time(14, 0) <= t < time(15, 0):
                return "ICT Silver Bullet PM (14:00-15:00 EST)"
            return "New York PM Session (13:30-16:00 EST)"

        # Silver Bullet AM Window: 10:00 - 11:00 EST
        if time(10, 0) <= t < time(11, 0):
            return "ICT Silver Bullet AM (10:00-11:00 EST)"

        # New York Open Kill Zone: 07:00 - 10:00 EST (Ep 4 & 8)
        if time(7, 0) <= t < time(10, 0):
            if time(9, 30) <= t < time(9, 45):
                return "New York Open (NYSE Bell Open 09:30 EST)"
            if time(8, 30) <= t < time(10, 0):
                return "New York Morning Hunt Window (08:30-10:00 EST)"
            return "New York Open Kill Zone (07:00-10:00 EST)"

        # London Close Kill Zone: 10:00 - 12:00 EST
        if time(10, 0) <= t < time(12, 0):
            return "London Close Kill Zone (10:00-12:00 EST)"

        # London Open Kill Zone: 02:00 - 05:00 EST (Ep 8)
        if time(2, 0) <= t < time(5, 0):
            return "London Open Kill Zone (02:00-05:00 EST)"

        # Asian Range: 20:00 - 00:00 EST
        if time(20, 0) <= t or t < time(0, 0):
            return "Asian Range (20:00-00:00 EST)"

        # Central Bank Dealers Range (CBDR): 14:00 - 20:00 EST
        if time(14, 0) <= t < time(20, 0):
            return "CBDR Range (14:00-20:00 EST)"

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
                "New York Morning",
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
