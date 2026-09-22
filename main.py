"""
Main runner for ICT Automated Multi-Asset Signal Engine.
Supports continuous daemon monitoring, one-shot scan, deterministic simulation,
and lightweight 24/7 cloud health dashboard server (Render/Railway/Fly.io compatible).
"""
import sys
import os
import time
import argparse
import logging
import threading
import json
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

from src.config.settings import AppConfig
from src.engine.fetcher import CryptoDataFetcher, MarketDataFetcher
from src.engine.detector import ICTSignalDetector
from src.alerts.telegram import TelegramNotifier
from src.alerts.discord import DiscordNotifier
from src.alerts.console import ConsoleNotifier
from src.core.models import Candle
from src.core.sessions import SessionDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ICT-Engine")

# Shared state for 24/7 cloud health checks and web dashboard
LATEST_STATE = {
    "status": "INITIALIZING",
    "last_scan_utc": "",
    "last_scan_ist": "",
    "active_session": "",
    "prices": {},
    "monitored_symbols": [],
}


class CloudHealthServer(BaseHTTPRequestHandler):
    """
    Lightweight HTTP server enabling 100% free hosting on Render/Railway/Fly.io.
    Provides /health endpoint for uptime monitors and / for a live status dashboard.
    """

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "service": "ict-multi-asset-signals"}).encode())
            return

        # HTML Live Status Dashboard
        prices_html = "".join(
            [
                f"<div style='background:#181f2e;padding:12px;border-radius:6px;margin-bottom:8px;display:flex;justify-content:space-between;'>"
                f"<span style='font-weight:600;'>{sym}</span>"
                f"<span style='color:#38bdf8;font-weight:bold;'>${price:,.2f}</span>"
                f"</div>"
                for sym, price in LATEST_STATE["prices"].items()
            ]
        )

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ICT Automated Signal Engine — 24/7 Cloud</title>
<style>
  body {{ background: #0b0e14; color: #d1d4dc; font-family: -apple-system, sans-serif; padding: 24px; max-width: 600px; margin: 0 auto; }}
  .card {{ background: #121722; border: 1px solid #1f2430; border-radius: 8px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
  .badge {{ background: #064e3b; color: #34d399; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
</style>
</head>
<body>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="margin:0;font-size:18px;color:#f0f3f6;">⚡ ICT 24/7 Signal Engine</h2>
      <span class="badge">● ONLINE 24/7</span>
    </div>
    <p style="margin:4px 0;font-size:13px;color:#94a3b8;"><b>Active Session:</b> {LATEST_STATE["active_session"]}</p>
    <p style="margin:4px 0;font-size:13px;color:#94a3b8;"><b>Last Scan (India):</b> {LATEST_STATE["last_scan_ist"]}</p>
    <hr style="border:0;border-top:1px solid #1f2430;margin:16px 0;">
    <h3 style="font-size:14px;color:#f0f3f6;margin-bottom:12px;">Live Market Prices</h3>
    {prices_html or "<p style='color:#64748b;font-size:13px;'>Starting first scan...</p>"}
    <div style="margin-top:20px;text-align:center;font-size:12px;color:#64748b;">
      Interbank Price Delivery Algorithm • ICT 2022 Mentorship Model
    </div>
  </div>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        # Silence console access logs to keep terminal output clean
        pass


def start_cloud_health_server(port: int = 8080):
    try:
        server = HTTPServer(("0.0.0.0", port), CloudHealthServer)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info(f"Cloud 24/7 Health Dashboard active on port {port} (http://0.0.0.0:{port})")
    except Exception as e:
        logger.warning(f"Could not bind cloud HTTP server on port {port}: {e}")


def run_demo():
    """
    Executes a deterministic demonstration of the ICT 2022 Mentorship + SMT Model
    matching the exact Bitcoin setup analyzed.
    """
    logger.info("Running deterministic ICT Demo Simulation...")
    detector = ICTSignalDetector(min_risk_reward=2.0)

    # 14:00 UTC = 10:00 AM EST (New York Morning Hunt Window 08:30 - 10:00 EST / 06:00 PM - 07:30 PM IST)
    base_time = datetime(2026, 9, 22, 14, 0, tzinfo=timezone.utc)

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
    logger.info("Scanning asset universe (Crypto & Commodities) for live ICT setups...")
    now_utc = datetime.now(timezone.utc)
    LATEST_STATE["status"] = "SCANNING"
    LATEST_STATE["last_scan_utc"] = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    LATEST_STATE["last_scan_ist"] = SessionDetector.to_ist_time(now_utc).strftime("%d %b %Y, %I:%M %p IST")
    LATEST_STATE["active_session"] = SessionDetector.get_active_session(now_utc)
    LATEST_STATE["monitored_symbols"] = config.symbols

    for symbol in config.symbols:
        try:
            # Determine appropriate SMT benchmark for the specific asset
            smt_benchmark = MarketDataFetcher.get_smt_benchmark_pair(symbol)
            smt_candles = None
            try:
                smt_candles = fetcher.fetch_candles(smt_benchmark, timeframe=config.ltf_timeframe, limit=50)
            except Exception:
                pass

            ltf = fetcher.fetch_candles(symbol, timeframe=config.ltf_timeframe, limit=60)
            htf = fetcher.fetch_candles(symbol, timeframe=config.htf_timeframe, limit=40)

            current_price = ltf[-1].close
            session = SessionDetector.get_active_session(ltf[-1].timestamp)
            LATEST_STATE["prices"][symbol] = current_price

            logger.info(f"Auditing order flow for {symbol} | Live Price: ${current_price:,.2f} | {session}")

            signal = detector.analyze_market(
                symbol=symbol,
                ltf_candles=ltf,
                htf_candles=htf,
                smt_candles=smt_candles,
                smt_symbol=smt_benchmark,
                timeframe=config.ltf_timeframe,
            )

            if signal:
                ConsoleNotifier.print_signal(signal)
                if config.telegram_bot_token:
                    TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id).send_signal(signal)
                if config.discord_webhook_url:
                    DiscordNotifier(config.discord_webhook_url).send_signal(signal)
            else:
                logger.info(f"  ↳ {symbol} (${current_price:,.2f}): In balance / No unresolved sweep & MSS. Standing aside.")

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")

    LATEST_STATE["status"] = "IDLE - WAITING FOR NEXT BAR"


def main():
    parser = argparse.ArgumentParser(description="ICT Automated Multi-Asset Signal Engine")
    parser.add_argument("--mode", choices=["run", "once", "demo"], default="demo", help="Execution mode")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    # Start Cloud Health & Live Dashboard on port specified by cloud provider or default 8080
    port = int(os.getenv("PORT", "8080"))
    start_cloud_health_server(port)

    if args.mode == "demo":
        run_demo()
        return

    config = AppConfig.load(args.config)
    fetcher = MarketDataFetcher(exchange_id="okx")
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
