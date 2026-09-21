"""
Main runner for ICT Automated Crypto Signals Engine.
Supports continuous daemon monitoring, one-shot scan, and deterministic ICT simulation.
"""
import sys
import time
import argparse
import logging
from datetime import datetime, timezone, timedelta

from src.config.settings import AppConfig
from src.engine.fetcher import CryptoDataFetcher
from src.engine.detector import ICTSignalDetector
from src.alerts.telegram import TelegramNotifier
from src.alerts.discord import DiscordNotifier
from src.alerts.console import ConsoleNotifier
from src.core.models import Candle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ICT-Engine")


def run_demo():
    """
    Executes a deterministic demonstration of the ICT 2022 Mentorship + SMT Model
    matching the exact Bitcoin setup analyzed.
    """
    logger.info("Running deterministic ICT Demo Simulation...")
    detector = ICTSignalDetector(min_risk_reward=2.0)

    base_time = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)  # 08:00 EST

    # Generate HTF 4H Candles (Dealing range $61,000 - $68,000)
    htf_candles = [
        Candle(base_time - timedelta(hours=i * 4), 62000, 68000, 61000, 63500, 5000)
        for i in range(25, 0, -1)
    ]

    # Generate 5M Candles simulating the session:
    ltf_candles = []
    t = base_time - timedelta(minutes=45 * 5)

    for i in range(25):
        price = 63600 + (100 if i % 4 in (0, 1) else -100)
        ltf_candles.append(Candle(t, price, price + 50, price - 50, price + 10, 150))
        t += timedelta(minutes=5)

    # Swing Low at $63,200 (Candle 25)
    ltf_candles.append(Candle(t, 63300, 63350, 63200, 63250, 200))
    t += timedelta(minutes=5)
    ltf_candles.append(Candle(t, 63250, 63450, 63240, 63400, 200))
    t += timedelta(minutes=5)
    # Swing High at $63,620 (Candle 27)
    ltf_candles.append(Candle(t, 63400, 63620, 63380, 63600, 250))
    t += timedelta(minutes=5)
    ltf_candles.append(Candle(t, 63600, 63610, 63450, 63480, 200))
    t += timedelta(minutes=5)

    # Judas Sweep candle at 08:30 EST (Candle 29): Low swept to $63,050
    ltf_candles.append(Candle(t, 63250, 63300, 63050, 63220, 600))
    t += timedelta(minutes=5)

    # Displacement Sequence with MSS (Candles 30-32)
    ltf_candles.append(Candle(t, 63220, 63350, 63200, 63320, 500))
    t += timedelta(minutes=5)
    ltf_candles.append(Candle(t, 63320, 63720, 63300, 63700, 1200))
    t += timedelta(minutes=5)
    ltf_candles.append(Candle(t, 63700, 63860, 63520, 63850, 900))
    t += timedelta(minutes=5)

    # SMT ETH Candles: Formed a Higher Low
    smt_candles = []
    t_eth = base_time - timedelta(minutes=45 * 5)
    for i in range(25):
        smt_candles.append(Candle(t_eth, 3350, 3360, 3310, 3320, 500))
        t_eth += timedelta(minutes=5)
    smt_candles.append(Candle(t_eth, 3320, 3330, 3310, 3315, 300))
    t_eth += timedelta(minutes=5)
    smt_candles.append(Candle(t_eth, 3315, 3340, 3315, 3335, 300))
    t_eth += timedelta(minutes=5)
    smt_candles.append(Candle(t_eth, 3335, 3350, 3330, 3345, 350))
    t_eth += timedelta(minutes=5)
    smt_candles.append(Candle(t_eth, 3345, 3348, 3335, 3340, 250))
    t_eth += timedelta(minutes=5)
    # ETH at 08:30 EST makes a Higher Low ($3,325 > $3,310)
    smt_candles.append(Candle(t_eth, 3340, 3342, 3325, 3338, 900))

    signal = detector.analyze_market(
        symbol="BTC/USDT",
        ltf_candles=ltf_candles,
        htf_candles=htf_candles,
        smt_candles=smt_candles,
        smt_symbol="ETH/USDT",
        timeframe="5m",
    )

    if signal:
        ConsoleNotifier.print_signal(signal)
    else:
        logger.warning("No setup met the strict institutional criteria.")


def scan_live(config: AppConfig, fetcher: CryptoDataFetcher, detector: ICTSignalDetector):
    logger.info("Scanning crypto pairs for live ICT setups...")

    # Fetch secondary benchmark for SMT
    smt_candles = None
    try:
        smt_candles = fetcher.fetch_candles(config.smt_benchmark, timeframe=config.ltf_timeframe, limit=50)
    except Exception as e:
        logger.warning(f"Failed to fetch SMT benchmark {config.smt_benchmark}: {e}")

    for symbol in config.symbols:
        try:
            logger.info(f"Auditing order flow for {symbol}...")
            ltf = fetcher.fetch_candles(symbol, timeframe=config.ltf_timeframe, limit=60)
            htf = fetcher.fetch_candles(symbol, timeframe=config.htf_timeframe, limit=40)

            signal = detector.analyze_market(
                symbol=symbol,
                ltf_candles=ltf,
                htf_candles=htf,
                smt_candles=smt_candles,
                smt_symbol=config.smt_benchmark,
                timeframe=config.ltf_timeframe,
            )

            if signal:
                ConsoleNotifier.print_signal(signal)
                if config.telegram_bot_token:
                    TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id).send_signal(signal)
                if config.discord_webhook_url:
                    DiscordNotifier(config.discord_webhook_url).send_signal(signal)
            else:
                logger.info(f"  ↳ {symbol}: Price is delivering within balance or no validated sweep/MSS. Standing aside.")

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")


def main():
    parser = argparse.ArgumentParser(description="ICT Automated Crypto Signal Engine")
    parser.add_argument("--mode", choices=["run", "once", "demo"], default="demo", help="Execution mode")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()
        return

    config = AppConfig.load(args.config)
    fetcher = CryptoDataFetcher(exchange_id="binance")
    detector = ICTSignalDetector(min_risk_reward=config.min_risk_reward)

    if args.mode == "once":
        scan_live(config, fetcher, detector)
        return

    logger.info("Starting continuous ICT Market Scanner...")
    while True:
        scan_live(config, fetcher, detector)
        time.sleep(config.scan_interval_seconds)


if __name__ == "__main__":
    main()
