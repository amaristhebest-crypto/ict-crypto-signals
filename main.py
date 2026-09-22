"""
Master execution runner for ICT multi-asset algorithmic scanning engine
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
from src.core.models import Candle, ICTSignal, Direction
from src.core.sessions import SessionDetector
from src.core.mffu import MFFUHelper

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
    "recent_signals": [],
}


def register_signal_state(signal: ICTSignal):
    """
    Saves detected signal with MFFU 50K contract metrics for web dashboard display.
    """
    ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
    ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")
    m = MFFUHelper.calculate_trade_metrics(
        signal.symbol,
        signal.entry_price,
        signal.stop_loss,
        signal.target_2,
        quantity=2,
    )

    sig_data = {
        "symbol": signal.symbol,
        "mffu_ticker": m["mffu_ticker"],
        "contract_name": m["contract_name"],
        "timeframe": signal.timeframe,
        "direction": signal.direction.value,
        "setup_name": signal.setup_name,
        "session_name": signal.session_name,
        "ist_time": ist_time,
        "ny_time": ny_time,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "target_1": signal.target_1,
        "target_2": signal.target_2,
        "target_3": signal.target_3,
        "risk_reward_ratio": signal.risk_reward_ratio,
        "risk_points": m["risk_points"],
        "dollar_risk": m["dollar_risk"],
        "dollar_profit": m["dollar_profit"],
        "cushion_pct": m["cushion_pct"],
        "tv_link": m["tv_url"],
        "confluences": signal.confluence_factors,
        "invalidation": signal.invalidation_notes,
    }

    # Keep latest 5 signals
    LATEST_STATE["recent_signals"].insert(0, sig_data)
    if len(LATEST_STATE["recent_signals"]) > 5:
        LATEST_STATE["recent_signals"].pop()


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
                f"<div style='background:#181f2e;padding:10px 14px;border-radius:6px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;'>"
                f"<span style='font-weight:600;font-size:14px;color:#e2e8f0;'>{sym}</span>"
                f"<span style='color:#38bdf8;font-weight:bold;font-family:monospace;font-size:14px;'>${price:,.2f}</span>"
                f"</div>"
                for sym, price in LATEST_STATE["prices"].items()
            ]
        )

        # Signals Card HTML (MFFU 50K Specific Execution)
        signals_html = ""
        if LATEST_STATE["recent_signals"]:
            for sig in LATEST_STATE["recent_signals"]:
                is_bull = sig["direction"] == "BULLISH"
                bg_card = "#0f231c" if is_bull else "#2a1215"
                border_card = "#10b981" if is_bull else "#ef4444"
                action_word = "BUY / LONG" if is_bull else "SELL / SHORT"
                order_name = "LIMIT BUY" if is_bull else "LIMIT SELL"

                signals_html += f"""
                <div style="background:{bg_card};border:1px solid {border_card};border-radius:8px;padding:16px;margin-bottom:16px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:16px;font-weight:bold;color:#f8fafc;">⚡ MFFU: {sig['mffu_ticker']} ({sig['contract_name']})</span>
                    <span style="background:{border_card};color:#000;font-weight:bold;padding:3px 8px;border-radius:4px;font-size:11px;">{action_word}</span>
                  </div>
                  <div style="font-size:12px;color:#94a3b8;margin:6px 0;">{sig['ist_time']} • {sig['session_name']}</div>

                  <div style="background:#131b28;border-radius:6px;padding:10px 14px;margin:8px 0;font-size:13px;">
                    <div>👉 <b>Tradovate Ticker:</b> <span style="color:#fbbf24;font-weight:bold;">{sig['mffu_ticker']}</span> (Micro contract)</div>
                    <div>👉 <b>Recommended Qty:</b> <span style="color:#f8fafc;font-weight:bold;">2 Micro Contracts</span></div>
                  </div>
                  
                  <div style="background:#0b0e14;border-radius:6px;padding:14px;margin:10px 0;font-size:14px;line-height:2.0;">
                    <div style="color:#f8fafc;font-weight:bold;margin-bottom:6px;border-bottom:1px solid #1e293b;padding-bottom:4px;">
                      🎯 3-Point Bracket Order (Copy & Paste):
                    </div>
                    <div>1️⃣ <b>ENTRY PRICE:</b> <span style="color:#38bdf8;font-weight:bold;font-family:monospace;font-size:15px;">${sig['entry_price']:,.2f}</span> ({order_name} at FVG CE)</div>
                    <div>2️⃣ <b>STOP LOSS:</b> <span style="color:#f87171;font-weight:bold;font-family:monospace;font-size:15px;">${sig['stop_loss']:,.2f}</span></div>
                    <div>3️⃣ <b>TAKE PROFIT:</b> <span style="color:#34d399;font-weight:bold;font-family:monospace;font-size:15px;">${sig['target_2']:,.2f}</span> (1 : {sig['risk_reward_ratio']:.1f} R:R)</div>
                    <div style="font-size:12px;color:#94a3b8;margin-top:6px;">💡 <i>Breakeven: Once price hits ${sig['target_1']:,.2f}, drag Stop Loss to ${sig['entry_price']:,.2f} (Risk-Free!)</i></div>
                  </div>

                  <div style="background:#131822;border-radius:6px;padding:10px 14px;font-size:12px;color:#cbd5e1;margin-bottom:10px;line-height:1.6;">
                    <b>💰 MFFU 50K Risk Check:</b><br>
                    • Dollar Risk on 2 Micros: <span style="color:#f87171;font-weight:bold;">${sig['dollar_risk']:,.2f}</span> (Only {sig['cushion_pct']:.1f}% of $2,000 drawdown floor)<br>
                    • Potential Profit: <span style="color:#34d399;font-weight:bold;">+${sig['dollar_profit']:,.2f}</span><br>
                    • Invalidation Floor: <b>$48,000.00</b> (EOD) &nbsp;|&nbsp; Daily Cap: <b>$1,500.00</b> (50% consistency)
                  </div>

                  <a href="{sig['tv_link']}" target="_blank" style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:6px 12px;border-radius:4px;font-size:12px;font-weight:bold;">
                    📈 Open Chart on TradingView &rarr;
                  </a>
                </div>
                """
        else:
            signals_html = "<div style='color:#64748b;font-size:13px;padding:10px;background:#131822;border-radius:6px;text-align:center;'>Waiting for next high-probability displacement & FVG setup...</div>"

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MFFU 50K — ICT Automated Signal Engine</title>
<style>
  body {{ background: #0b0e14; color: #d1d4dc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 16px; max-width: 650px; margin: 0 auto; }}
  .card {{ background: #121722; border: 1px solid #1f2430; border-radius: 10px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
  .badge {{ background: #064e3b; color: #34d399; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
  hr {{ border:0; border-top: 1px solid #1f2430; margin: 16px 0; }}
</style>
</head>
<body>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h2 style="margin:0;font-size:18px;color:#f0f3f6;">⚡ MFFU 50K Signal Engine</h2>
      <span class="badge">● ONLINE 24/7</span>
    </div>
    <p style="margin:4px 0;font-size:13px;color:#94a3b8;"><b>Active Session:</b> {LATEST_STATE["active_session"]}</p>
    <p style="margin:4px 0;font-size:13px;color:#94a3b8;"><b>Last Scan (India):</b> {LATEST_STATE["last_scan_ist"]}</p>

    <!-- MFFU 50K Account Parameters Guard Box -->
    <div style="background:#141c2b;border:1px solid #2563eb;border-radius:8px;padding:14px;margin:14px 0;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-weight:bold;color:#60a5fa;font-size:13px;">🏛 MFFU $50,000 ACCOUNT GUARD</span>
        <span style="background:#2563eb;color:#fff;font-size:10px;font-weight:bold;padding:2px 8px;border-radius:4px;">END-OF-DAY EOD</span>
      </div>
      <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;line-height:1.6;">
        <div>• Account Capital: <b>$50,000.00</b></div>
        <div>• Target (+6%): <b style="color:#34d399;">+$3,000.00 ($53k)</b></div>
        <div>• Invalidation Floor: <b style="color:#f87171;">$48,000.00 (EOD)</b></div>
        <div>• 50% Daily Profit Cap: <b>$1,500.00 Max</b></div>
      </div>
      <div style="margin-top:10px;padding-top:8px;border-top:1px solid #1e293b;font-size:11px;color:#cbd5e1;line-height:1.7;">
        <b>Tradovate Tickers:</b> <span style="color:#fbbf24;font-weight:bold;">MNQ</span> (Nasdaq) &nbsp;|&nbsp; <span style="color:#fbbf24;font-weight:bold;">MGC</span> (Gold) &nbsp;|&nbsp; <span style="color:#fbbf24;font-weight:bold;">MBT</span> (Bitcoin) &nbsp;|&nbsp; <span style="color:#fbbf24;font-weight:bold;">MCL</span> (Crude)<br>
        <b>Strict Position Sizing:</b> Always trade <b>2 to 3 Micro Contracts</b> (Never full Minis!)
      </div>
    </div>
    
    <hr>
    <h3 style="font-size:14px;color:#f0f3f6;margin:0 0 10px 0;">⚡ MFFU Active Trade Execution Plans</h3>
    {signals_html}

    <hr>
    <h3 style="font-size:14px;color:#f0f3f6;margin:0 0 10px 0;">Live Market Universe</h3>
    {prices_html or "<p style='color:#64748b;font-size:13px;'>Starting first scan...</p>"}

    <div style="margin-top:20px;text-align:center;font-size:11px;color:#64748b;">
      My Funded Futures (MFFU) Algorithmic Model • ICT 2022 Mentorship
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
        register_signal_state(signal)
        ConsoleNotifier.print_signal(signal)
    else:
        logger.warning("No setup met the strict institutional criteria.")


def scan_live(config: AppConfig, fetcher: CryptoDataFetcher, detector: ICTSignalDetector):
    logger.info("Scanning asset universe (Crypto, Commodities & US Index Futures) for live ICT setups...")
    now_utc = datetime.now(timezone.utc)
    LATEST_STATE["status"] = "SCANNING"
    LATEST_STATE["last_scan_utc"] = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    LATEST_STATE["last_scan_ist"] = SessionDetector.to_ist_time(now_utc).strftime("%d %b %Y, %I:%M %p IST")
    LATEST_STATE["active_session"] = SessionDetector.get_active_session(now_utc)
    LATEST_STATE["monitored_symbols"] = config.symbols

    for symbol in config.symbols:
        try:
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
                register_signal_state(signal)
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
        try:
            scan_live(config, fetcher, detector)
        except Exception as e:
            logger.error(f"Unhandled error in scan cycle: {e}")
        time.sleep(config.scan_interval_seconds)


if __name__ == "__main__":
    main()
