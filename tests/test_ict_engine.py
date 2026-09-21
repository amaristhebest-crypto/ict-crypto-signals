"""
Unit tests for the ICT Automated Crypto Signal Engine.
"""
import unittest
from datetime import datetime, timezone, timedelta
from src.core.models import Candle, Direction, SwingPoint
from src.core.sessions import SessionDetector
from src.core.pd_arrays import PDArrayEngine
from src.core.market_structure import MarketStructureAnalyzer
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

    def test_smt_divergence(self):
        t = datetime.now()
        # BTC makes Lower Low: 63200 -> 63050
        btc = [
            Candle(t - timedelta(minutes=20), 63300, 63400, 63200, 63250, 100),
            Candle(t - timedelta(minutes=15), 63250, 63500, 63220, 63450, 100),
            Candle(t - timedelta(minutes=10), 63450, 63600, 63400, 63550, 100),
            Candle(t - timedelta(minutes=5), 63550, 63560, 63300, 63320, 100),
            Candle(t, 63320, 63350, 63050, 63200, 200),
        ]
        # ETH makes Higher Low: 3310 -> 3325
        eth = [
            Candle(t - timedelta(minutes=20), 3330, 3340, 3310, 3315, 100),
            Candle(t - timedelta(minutes=15), 3315, 3350, 3312, 3340, 100),
            Candle(t - timedelta(minutes=10), 3340, 3360, 3335, 3350, 100),
            Candle(t - timedelta(minutes=5), 3350, 3355, 3340, 3345, 100),
            Candle(t, 3345, 3350, 3325, 3335, 200),
        ]
        smt = SMTDivergenceDetector.analyze(btc, eth, lookback=10)
        # Verify SMT structure analyzer returns SMTResult
        self.assertIsNotNone(smt)

    def test_drawdown_risk_halving_rule(self):
        rm = ICTRiskManager(initial_risk_percent=1.0)
        self.assertEqual(rm.current_risk_pct, 1.0)

        # 1 Loss -> Risk stays 1.0%
        rm.record_trade_result(is_win=False)
        self.assertEqual(rm.current_risk_pct, 1.0)

        # 2 Consecutive Losses -> Risk halved to 0.5%
        rm.record_trade_result(is_win=False)
        self.assertEqual(rm.current_risk_pct, 0.5)

        # 1 Win -> Risk remains at 0.5% until 2 consecutive wins
        rm.record_trade_result(is_win=True)
        self.assertEqual(rm.current_risk_pct, 0.5)

        # 2nd Win -> Risk restored back to 1.0%
        rm.record_trade_result(is_win=True)
        self.assertEqual(rm.current_risk_pct, 1.0)

    def test_ote_levels(self):
        ote = ICTRiskManager.calculate_ote_levels(63050, 63850, Direction.BULLISH)
        self.assertAlmostEqual(ote["equilibrium"], 63450.0)
        self.assertAlmostEqual(ote["ote_705"], 63850 - (800 * 0.705), places=2)
        self.assertGreater(ote["ext_027"], 63850)


if __name__ == "__main__":
    unittest.main()
