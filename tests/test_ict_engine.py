"""
Unit tests for the ICT Automated Crypto Signal Engine.
Validates exact rules from the 2022 Mentorship & Core Content.
"""
import unittest
from datetime import datetime, timezone, timedelta, time
import zoneinfo
from src.core.models import Candle, Direction, FairValueGap
from src.core.sessions import SessionDetector, NY_TZ
from src.core.pd_arrays import PDArrayEngine
from src.core.smt import SMTDivergenceDetector
from src.core.risk_manager import ICTRiskManager
from src.engine.detector import ICTSignalDetector


class TestICTEngine(unittest.TestCase):
    def test_fvg_consequent_encroachment(self):
        c1 = Candle(datetime.now(), 63000, 63300, 62900, 63200, 100)
        c2 = Candle(datetime.now(), 63200, 63700, 63150, 63650, 500)
        c3 = Candle(datetime.now(), 63650, 63900, 63500, 63800, 200)

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

    def test_drawdown_risk_halving_rule(self):
        rm = ICTRiskManager(initial_risk_percent=1.0)
        self.assertEqual(rm.current_risk_pct, 1.0)
        rm.record_trade_result(is_win=False)
        self.assertEqual(rm.current_risk_pct, 1.0)
        rm.record_trade_result(is_win=False)
        self.assertEqual(rm.current_risk_pct, 0.5)
        rm.record_trade_result(is_win=True)
        self.assertEqual(rm.current_risk_pct, 0.5)
        rm.record_trade_result(is_win=True)
        self.assertEqual(rm.current_risk_pct, 1.0)

    def test_ote_levels(self):
        ote = ICTRiskManager.calculate_ote_levels(63050, 63850, Direction.BULLISH)
        self.assertAlmostEqual(ote["equilibrium"], 63450.0)
        self.assertAlmostEqual(ote["ote_705"], 63850 - (800 * 0.705), places=2)
        self.assertGreater(ote["ext_027"], 63850)

    def test_ep41_two_bounce_fvg_rule(self):
        """Ep 41: FVG can be tested at most twice. 3rd bounce is exhausted."""
        fvg = FairValueGap(63500, 63300, 63400, Direction.BULLISH, 0, datetime.now())
        c_touch1 = Candle(datetime.now(), 63600, 63650, 63350, 63550, 100) # 1st bounce
        c_touch2 = Candle(datetime.now(), 63550, 63600, 63380, 63580, 100) # 2nd bounce
        c_touch3 = Candle(datetime.now(), 63580, 63600, 63390, 63520, 100) # 3rd bounce

        c_away = Candle(datetime.now(), 63700, 63800, 63600, 63750, 100)  # fully above the FVG

        # Consecutive candles inside the gap = ONE visit, not one bounce per candle.
        res_cont = ICTSignalDetector.audit_fvg_lifecycle(fvg, [c_touch1, c_touch2, c_touch3], target_1=64000, direction=Direction.BULLISH)
        self.assertTrue(res_cont["is_valid"])
        self.assertEqual(res_cont["bounces"], 1)

        # Two SEPARATE visits (price leaves the gap in between) = 2 bounces: still valid.
        res2 = ICTSignalDetector.audit_fvg_lifecycle(fvg, [c_touch1, c_away, c_touch2], target_1=64000, direction=Direction.BULLISH)
        self.assertTrue(res2["is_valid"])
        self.assertEqual(res2["bounces"], 2)

        # A genuine 3rd visit is exhausted per Ep 41.
        seq = [c_touch1, c_away, c_touch2, c_away, c_touch3]
        res_real = ICTSignalDetector.audit_fvg_lifecycle(fvg, seq, target_1=64000, direction=Direction.BULLISH)
        self.assertFalse(res_real["is_valid"])
        self.assertEqual(res_real["bounces"], 3)

    def test_ep5_ny_lunch_dead_zone(self):
        """Ep 5 & 39: 12:00 - 13:00 EST is a strict No-Trade Dead Zone."""
        lunch_dt = datetime(2026, 9, 22, 12, 30, tzinfo=NY_TZ)
        self.assertFalse(SessionDetector.is_killzone_active(lunch_dt))
        session_name = SessionDetector.get_active_session(lunch_dt)
        self.assertIn("DO NOT TRADE", session_name)


if __name__ == "__main__":
    unittest.main()
