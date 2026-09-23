"""
Unit tests for the ICT signal engine.

FIXED 2026-09-23 — the two-bounce test previously ENSHRINED the bug. It fed
three CONSECUTIVE candles resting inside the FVG and asserted that counted as
three bounces. That is one retest spanning fifteen minutes, not three bounces,
and the assertion would have blocked anyone from ever fixing the counter.

Added: a regression test for the MSS direction bug, which had no coverage at
all despite being the most damaging defect in the engine.
"""
import unittest
from datetime import datetime, timezone, timedelta

from src.core.models import Candle, Direction, FairValueGap
from src.core.sessions import SessionDetector, NY_TZ
from src.core.pd_arrays import PDArrayEngine
from src.core.market_structure import MarketStructureAnalyzer
from src.core.risk_manager import ICTRiskManager
from src.engine.detector import ICTSignalDetector


def _c(o, h, l, c, v=100, t=None):
    return Candle(t or datetime.now(timezone.utc), o, h, l, c, v)


class TestICTEngine(unittest.TestCase):

    def test_fvg_consequent_encroachment(self):
        c1 = _c(63000, 63300, 62900, 63200)
        c2 = _c(63200, 63700, 63150, 63650, 500)
        c3 = _c(63650, 63900, 63500, 63800, 200)

        fvgs = PDArrayEngine.find_fair_value_gaps([c1, c2, c3])
        self.assertEqual(len(fvgs), 1)
        fvg = fvgs[0]
        self.assertEqual(fvg.direction, Direction.BULLISH)
        self.assertEqual(fvg.bottom, 63300)
        self.assertEqual(fvg.top, 63500)
        self.assertEqual(fvg.consequent_encroachment, 63400.0)

    def test_equilibrium_calculation(self):
        eq = PDArrayEngine.calculate_equilibrium(68000, 61000)
        self.assertEqual(eq, 64500.0)
        self.assertTrue(PDArrayEngine.is_in_discount(63000, 68000, 61000))
        self.assertFalse(PDArrayEngine.is_in_discount(66000, 68000, 61000))

    def test_ote_levels(self):
        ote = ICTRiskManager.calculate_ote_levels(63050, 63850, Direction.BULLISH)
        self.assertAlmostEqual(ote["equilibrium"], 63450.0)
        self.assertAlmostEqual(ote["ote_705"], 63850 - (800 * 0.705), places=2)
        self.assertGreater(ote["ext_027"], 63850)
        # ext_100 is always the largest, so max(ext_062, ext_100) can never
        # select ext_062. Documented so nobody "fixes" target_3 back.
        self.assertGreater(ote["ext_100"], ote["ext_062"])

    # ------------------------------------------------------------------
    def test_ep41_consecutive_candles_are_one_bounce(self):
        """Three candles resting inside the gap is ONE visit, not three bounces."""
        fvg = FairValueGap(63500, 63300, 63400, Direction.BULLISH, 0, datetime.now(timezone.utc))
        inside_1 = _c(63600, 63650, 63350, 63550)
        inside_2 = _c(63550, 63600, 63380, 63580)
        inside_3 = _c(63580, 63600, 63390, 63520)

        res = ICTSignalDetector.audit_fvg_lifecycle(
            fvg, [inside_1, inside_2, inside_3], target_1=64000, direction=Direction.BULLISH
        )
        self.assertEqual(res["bounces"], 1)
        self.assertTrue(res["is_valid"])

    def test_ep41_third_genuine_bounce_invalidates(self):
        """A real bounce requires price to LEAVE the gap between visits."""
        fvg = FairValueGap(63500, 63300, 63400, Direction.BULLISH, 0, datetime.now(timezone.utc))
        inside = _c(63600, 63650, 63350, 63550)
        away = _c(63700, 63800, 63600, 63750)     # entirely above the gap

        seq = [inside, away, inside, away, inside]
        res = ICTSignalDetector.audit_fvg_lifecycle(
            fvg, seq, target_1=64000, direction=Direction.BULLISH
        )
        self.assertEqual(res["bounces"], 3)
        self.assertFalse(res["is_valid"])

    # ------------------------------------------------------------------
    def test_mss_respects_required_direction(self):
        """
        Regression for the premature-termination bug: a counter-direction shift
        occurring first must not consume the search window.
        """
        t0 = datetime(2026, 9, 22, 13, 0, tzinfo=timezone.utc)
        candles, swings = [], []

        # Quiet base so the displacement test has something to compare against.
        for i in range(12):
            candles.append(_c(100, 101, 99, 100, 100, t0 + timedelta(minutes=5 * i)))

        # A swing high at index 12 and a swing low at index 16.
        candles.append(_c(100, 110, 99, 109, 100, t0 + timedelta(minutes=60)))   # idx 12
        for i in range(13, 16):
            candles.append(_c(100, 101, 99, 100, 100, t0 + timedelta(minutes=5 * i)))
        candles.append(_c(100, 101, 90, 91, 100, t0 + timedelta(minutes=80)))    # idx 16

        from src.core.models import SwingPoint
        swings.append(SwingPoint(index=12, timestamp=candles[12].timestamp, price=110, is_high=True))
        swings.append(SwingPoint(index=16, timestamp=candles[16].timestamp, price=90, is_high=False))

        # Bar 18: a big DOWN candle closing below the swing low -> bearish MSS.
        # Bar 19: a big UP candle closing above the swing high -> bullish MSS.
        candles.append(_c(100, 101, 99, 100, 100, t0 + timedelta(minutes=85)))   # idx 17
        candles.append(_c(95, 96, 80, 81, 100, t0 + timedelta(minutes=90)))      # idx 18
        candles.append(_c(85, 130, 84, 129, 100, t0 + timedelta(minutes=95)))    # idx 19

        # Legacy behaviour: first match wins, so this returns BEARISH.
        legacy = MarketStructureAnalyzer.detect_market_structure_shift(
            candles, swings, sweep_index=17, search_window=12
        )
        self.assertIsNotNone(legacy)
        self.assertEqual(legacy[1], Direction.BEARISH)

        # Fixed behaviour: asking for BULLISH skips the bearish bar and finds
        # the bullish MSS two bars later, instead of returning None.
        bullish = MarketStructureAnalyzer.detect_market_structure_shift(
            candles, swings, sweep_index=17, search_window=12,
            required_direction=Direction.BULLISH,
        )
        self.assertIsNotNone(bullish, "bullish MSS was missed - direction filter not applied")
        self.assertEqual(bullish[1], Direction.BULLISH)

    # ------------------------------------------------------------------
    def test_ep5_ny_lunch_dead_zone(self):
        lunch_dt = datetime(2026, 9, 22, 12, 30, tzinfo=NY_TZ)
        self.assertFalse(SessionDetector.is_killzone_active(lunch_dt))
        self.assertIn("DO NOT TRADE", SessionDetector.get_active_session(lunch_dt))

    def test_displacement_fails_closed_on_empty_window(self):
        """An empty lookback used to return True, treating everything as displaced."""
        self.assertFalse(MarketStructureAnalyzer.check_displacement(_c(100, 110, 90, 109), []))


if __name__ == "__main__":
    unittest.main()
