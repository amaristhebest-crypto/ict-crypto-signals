"""
Master execution runner for the ICT multi-asset scanning engine, plus a
lightweight 24/7 cloud dashboard (Render / Railway / Fly.io compatible).

FIXED 2026-09-23:
  C1  --mode now defaults to "run", not "demo". `python main.py` used to serve
      a fabricated BTC setup.
  C2  Demo signals are flagged and the dashboard shows a loud banner. You
      previously looked at a $63,435 demo entry while BTC was $85,000 and only
      caught it because the price was obviously stale.
  H6  LATEST_STATE["prices"] was iterated on the HTTP thread while the scan
      thread wrote to it — RuntimeError: dictionary changed size during
      iteration, i.e. random 500s. Now snapshotted.
  H4  LTF limit raised 60 -> 288 (24h of 5m). With a 5-hour window the NY
      Midnight Open candle was never present during an evening IST session, so
      get_ny_midnight_open() silently returned candles[0].open — an arbitrary
      price from five hours earlier, printed as a confluence.
  H7  Hardcoded "EDT" replaced with %Z, which is correct year-round.
  NEW Staleness guard: weekend/holiday Yahoo data is skipped, not scanned.
  NEW Rejection funnel printed after every scan.
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
from src.engine.fetcher import MarketDataFetcher, is_stale
from src.engine.detector import ICTSignalDetector, REJECTIONS, reset_rejections
from src.alerts.telegram import TelegramNotifier
from src.alerts.discord import DiscordNotifier
from src.alerts.console import ConsoleNotifier
from src.core.models import Candle, ICTSignal
from src.core.sessions import SessionDetector
from src.core.mffu import MFFUHelper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ICT-Engine")

LATEST_STATE = {
    "status": "INITIALIZING",
    "last_scan_utc": "",
    "last_scan_ist": "",
    "active_session": "",
    "prices": {},
    "monitored_symbols": [],
    "recent_signals": [],
    "is_demo": False,
    "last_funnel": "",
}


def register_signal_state(signal: ICTSignal, is_demo: bool = False):
    ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
    ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p %Z")
    m = MFFUHelper.calculate_trade_metrics(
        signal.symbol, signal.entry_price, signal.stop_loss, signal.target_2, quantity=2,
    )

    LATEST_STATE["recent_signals"].insert(0, {
        "symbol": signal.symbol,
        "mffu_ticker": m["mffu_ticker"],
        "contract_name": m["contract_name"],
        "tradeable": m.get("tradeable", True),
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
        "is_demo": is_demo,
    })
    if len(LATEST_STATE["recent_signals"]) > 5:
        LATEST_STATE["recent_signals"].pop()


class CloudHealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "service": "ict-multi-asset-signals"}).encode())
            return

        # FIXED (H6): snapshot before iterating. The scan thread mutates these.
        prices = dict(LATEST_STATE["prices"])
        signals = list(LATEST_STATE["recent_signals"])
        is_demo = LATEST_STATE["is_demo"]
        funnel = LATEST_STATE["last_funnel"]

        prices_html = "".join(
            f"<div style='background:#181f2e;padding:10px 14px;border-radius:6px;margin-bottom:6px;"
            f"display:flex;justify-content:space-between;align-items:center;'>"
            f"<span style='font-weight:600;font-size:14px;color:#e2e8f0;'>{sym}</span>"
            f"<span style='color:#38bdf8;font-weight:bold;font-family:monospace;font-size:14px;'>${price:,.2f}</span>"
            f"</div>"
            for sym, price in prices.items()
        )

        demo_banner = ""
        if is_demo:
            demo_banner = (
                "<div style='background:#7c2d12;border:2px solid #f97316;border-radius:8px;"
                "padding:14px;margin-bottom:14px;color:#fed7aa;font-weight:bold;text-align:center;'>"
                "&#9888; DEMO MODE &mdash; every signal below is FABRICATED from hardcoded "
                "candles. Do not trade these numbers."
                "</div>"
            )

        signals_html = ""
        if signals:
            for sig in signals:
                is_bull = sig["direction"] == "BULLISH"
                bg_card = "#0f231c" if is_bull else "#2a1215"
                border_card = "#10b981" if is_bull else "#ef4444"
                action_word = "BUY / LONG" if is_bull else "SELL / SHORT"
                order_name = "LIMIT BUY" if is_bull else "LIMIT SELL"

                demo_tag = ""
                if sig.get("is_demo"):
                    demo_tag = ("<span style='background:#f97316;color:#000;font-weight:bold;"
                                "padding:2px 8px;border-radius:4px;font-size:10px;'>DEMO &mdash; NOT REAL</span> ")

                if not sig.get("tradeable", True):
                    order_block = (
                        "<div style='background:#4c1d1d;border:1px solid #ef4444;border-radius:6px;"
                        "padding:12px;margin:10px 0;color:#fecaca;font-size:13px;'>"
                        "<b>&#9888; NOT TRADEABLE ON MFFU.</b> No CME futures contract exists for this "
                        "instrument. Analysis / SMT reference only &mdash; do not place an order."
                        "</div>"
                    )
                else:
                    order_block = f"""
                    <div style="background:#0b0e14;border-radius:6px;padding:14px;margin:10px 0;font-size:14px;line-height:2.0;">
                      <div style="color:#f8fafc;font-weight:bold;margin-bottom:6px;border-bottom:1px solid #1e293b;padding-bottom:4px;">
                        3-Point Bracket Order:
                      </div>
                      <div>1. <b>ENTRY:</b> <span style="color:#38bdf8;font-weight:bold;font-family:monospace;font-size:15px;">${sig['entry_price']:,.2f}</span> ({order_name} at FVG CE)</div>
                      <div>2. <b>STOP LOSS:</b> <span style="color:#f87171;font-weight:bold;font-family:monospace;font-size:15px;">${sig['stop_loss']:,.2f}</span></div>
                      <div>3. <b>TAKE PROFIT:</b> <span style="color:#34d399;font-weight:bold;font-family:monospace;font-size:15px;">${sig['target_2']:,.2f}</span> (1 : {sig['risk_reward_ratio']:.2f} R:R)</div>
                      <div style="font-size:12px;color:#94a3b8;margin-top:6px;">R:R is measured against this take profit, not a further target.</div>
                    </div>"""

                signals_html += f"""
                <div style="background:{bg_card};border:1px solid {border_card};border-radius:8px;padding:16px;margin-bottom:16px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:16px;font-weight:bold;color:#f8fafc;">{demo_tag}{sig['mffu_ticker']} ({sig['contract_name']})</span>
                    <span style="background:{border_card};color:#000;font-weight:bold;padding:3px 8px;border-radius:4px;font-size:11px;">{action_word}</span>
                  </div>
                  <div style="font-size:12px;color:#94a3b8;margin:6px 0;">{sig['ist_time']} &bull; {sig['session_name']}</div>
                  {order_block}
                  <div style="background:#131822;border-radius:6px;padding:10px 14px;font-size:12px;color:#cbd5e1;margin-bottom:10px;line-height:1.6;">
                    <b>Risk check (2 micros):</b>

                    &bull; Dollar risk: <span style="color:#f87171;font-weight:bold;">${sig['dollar_risk']:,.2f}</span>

                    &bull; Potential profit: <span style="color:#34d399;font-weight:bold;">+${sig['dollar_profit']:,.2f}</span>

                    &bull; EOD floor: <b>$48,000.00</b>  |  Daily cap: <b>$1,500.00</b>
                  </div>
                  <a href="{sig['tv_link']}" target="_blank" style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:6px 12px;border-radius:4px;font-size:12px;font-weight:bold;">Open chart &rarr;</a>
                </div>"""
        else:
            signals_html = ("<div style='color:#64748b;font-size:13px;padding:10px;background:#131822;"
                            "border-radius:6px;text-align:center;'>No qualifying setup. This is the normal state.</div>")

        funnel_html = ""
        if funnel:
            funnel_html = (
                "<hr><h3 style='font-size:13px;color:#f0f3f6;margin:0 0 8px 0;'>Why nothing fired</h3>"
                f"<div style='background:#131822;border-radius:6px;padding:10px 14px;font-size:12px;"
                f"color:#94a3b8;font-family:monospace;line-height:1.7;'>{funnel}</div>"
            )

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MFFU 50K - ICT Signal Engine</title>
<style>
 body {{ background:#0b0e14; color:#d1d4dc; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; padding:16px; max-width:650px; margin:0 auto; }}
 .card {{ background:#121722; border:1px solid #1f2430; border-radius:10px; padding:20px; }}
 .badge {{ background:#064e3b; color:#34d399; padding:4px 10px; border-radius:4px; font-weight:bold; font-size:12px; }}
 hr {{ border:0; border-top:1px solid #1f2430; margin:16px 0; }}
</style></head><body>
 <div class="card">
  {demo_banner}
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
   <h2 style="margin:0;font-size:18px;color:#f0f3f6;">MFFU 50K Signal Engine</h2>
   <span class="badge">{'DEMO' if is_demo else 'LIVE'}</span>
  </div>
  <p style="margin:4px 0;font-size:13px;color:#94a3b8;"><b>Active Session:</b> {LATEST_STATE["active_session"]}</p>
  <p style="margin:4px 0;font-size:13px;color:#94a3b8;"><b>Last Scan (India):</b> {LATEST_STATE["last_scan_ist"]}</p>
  <hr>
  <h3 style="font-size:14px;color:#f0f3f6;margin:0 0 10px 0;">Active Trade Plans</h3>
  {signals_html}
  {funnel_html}
  <hr>
  <h3 style="font-size:14px;color:#f0f3f6;margin:0 0 10px 0;">Live Market Universe</h3>
  {prices_html or "<p style='color:#64748b;font-size:13px;'>Starting first scan...</p>"}
 </div></body></html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, fmt, *args):
        pass


def start_cloud_health_server(port: int = 8080):
    try:
        server = HTTPServer(("0.0.0.0", port), CloudHealthServer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f"Dashboard active on port {port}")
    except Exception as e:
        logger.warning(f"Could not bind HTTP server on port {port}: {e}")


def run_demo():
    logger.warning("=" * 70)
    logger.warning("DEMO MODE - all output below is FABRICATED from hardcoded candles.")
    logger.warning("It is NOT live market data. Do not trade these numbers.")
    logger.warning("For live scanning use:  python main.py --mode run")
    logger.warning("=" * 70)
    LATEST_STATE["is_demo"] = True

    detector = ICTSignalDetector(min_risk_reward=2.0)
    base_time = datetime(2026, 9, 22, 14, 0, tzinfo=timezone.utc)  # 14:00 UTC = 10:00 NY (EDT)

    htf_candles = [
        Candle(base_time - timedelta(hours=i * 4), 62000, 68000, 61000, 63500, 5000)
        for i in range(25, 0, -1)
    ]

    ltf_candles = []
    t = base_time - timedelta(minutes=45 * 5)
    for i in range(25):
        price = 63600 + (100 if i % 4 in (0, 1) else -100)
        ltf_candles.append(Candle(t, price, price + 50, price - 50, price + 10, 150))
        t += timedelta(minutes=5)

    for o, h, l, c, v in [
        (63300, 63350, 63200, 63250, 200),
        (63250, 63450, 63240, 63400, 200),
        (63400, 63620, 63380, 63600, 250),
        (63600, 63610, 63450, 63480, 200),
        (63250, 63300, 63050, 63220, 600),   # Judas sweep
        (63220, 63350, 63200, 63320, 500),
        (63320, 63720, 63300, 63700, 1200),  # displacement
        (63700, 63860, 63520, 63850, 900),
    ]:
        ltf_candles.append(Candle(t, o, h, l, c, v))
        t += timedelta(minutes=5)

    smt_candles = []
    t_eth = base_time - timedelta(minutes=45 * 5)
    for i in range(25):
        smt_candles.append(Candle(t_eth, 3350, 3360, 3310, 3320, 500))
        t_eth += timedelta(minutes=5)
    for o, h, l, c, v in [
        (3320, 3330, 3310, 3315, 300), (3315, 3340, 3315, 3335, 300),
        (3335, 3350, 3330, 3345, 350), (3345, 3348, 3335, 3340, 250),
        (3340, 3342, 3325, 3338, 900),
    ]:
        smt_candles.append(Candle(t_eth, o, h, l, c, v))
        t_eth += timedelta(minutes=5)

    reset_rejections()
    signal = detector.analyze_market(
        symbol="BTC/USDT", ltf_candles=ltf_candles, htf_candles=htf_candles,
        smt_candles=smt_candles, smt_symbol="ETH/USDT", timeframe="5m",
    )

    if signal:
        register_signal_state(signal, is_demo=True)
        ConsoleNotifier.print_signal(signal)
        logger.warning(">>> The signal above is FABRICATED. Demo mode. <<<")
    else:
        logger.warning("No setup met the criteria.")
        if REJECTIONS:
            logger.info("REJECTION FUNNEL -> " + " | ".join(
                f"{k}: {v}" for k, v in sorted(REJECTIONS.items(), key=lambda x: -x[1])))


def scan_live(config: AppConfig, fetcher: MarketDataFetcher, detector: ICTSignalDetector):
    logger.info("Scanning asset universe for live ICT setups...")
    reset_rejections()

    now_utc = datetime.now(timezone.utc)
    LATEST_STATE["status"] = "SCANNING"
    LATEST_STATE["is_demo"] = False
    LATEST_STATE["last_scan_utc"] = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    LATEST_STATE["last_scan_ist"] = SessionDetector.to_ist_time(now_utc).strftime("%d %b %Y, %I:%M %p IST")
    LATEST_STATE["active_session"] = SessionDetector.get_active_session(now_utc)
    LATEST_STATE["monitored_symbols"] = config.symbols

    for symbol in config.symbols:
        try:
            smt_benchmark = MarketDataFetcher.get_smt_benchmark_pair(symbol)
            smt_candles = None
            try:
                smt_candles = fetcher.fetch_candles(smt_benchmark, timeframe=config.ltf_timeframe, limit=60)
            except Exception:
                pass

            # FIXED (H4): 288 bars of 5m = 24h, so the NY midnight candle is
            # actually present. Was 60 (5 hours) and the lookup always failed.
            ltf = fetcher.fetch_candles(symbol, timeframe=config.ltf_timeframe, limit=288)
            htf = fetcher.fetch_candles(symbol, timeframe=config.htf_timeframe, limit=40)

            if not ltf:
                logger.warning(f"  {symbol}: no data returned. Skipping.")
                continue

            # NEW: weekend / holiday guard. Yahoo serves Friday bars all weekend.
            if is_stale(ltf, config.ltf_timeframe):
                age = datetime.now(timezone.utc) - ltf[-1].timestamp
                logger.warning(f"  {symbol}: data is stale ({age}). Market closed. Skipping.")
                continue

            current_price = ltf[-1].close
            session = SessionDetector.get_active_session(ltf[-1].timestamp)
            LATEST_STATE["prices"][symbol] = current_price

            logger.info(f"Auditing {symbol} | ${current_price:,.2f} | {session}")

            signal = detector.analyze_market(
                symbol=symbol, ltf_candles=ltf, htf_candles=htf,
                smt_candles=smt_candles, smt_symbol=smt_benchmark,
                timeframe=config.ltf_timeframe,
            )

            if signal:
                register_signal_state(signal, is_demo=False)
                ConsoleNotifier.print_signal(signal)
                if config.telegram_bot_token:
                    TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id).send_signal(signal)
                if config.discord_webhook_url:
                    DiscordNotifier(config.discord_webhook_url).send_signal(signal)
            else:
                logger.info(f"  -> {symbol} (${current_price:,.2f}): standing aside.")

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")

    if REJECTIONS:
        summary = " | ".join(f"{k}: {v}" for k, v in sorted(REJECTIONS.items(), key=lambda x: -x[1]))
        logger.info(f"  REJECTION FUNNEL -> {summary}")
        LATEST_STATE["last_funnel"] = summary.replace(" | ", "\n")

    LATEST_STATE["status"] = "IDLE - WAITING FOR NEXT BAR"


def main():
    parser = argparse.ArgumentParser(description="ICT Automated Multi-Asset Signal Engine")
    # FIXED (C1): was default="demo".
    parser.add_argument("--mode", choices=["run", "once", "demo"], default="run",
                        help="run = continuous, once = single scan, demo = FABRICATED sample data")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    start_cloud_health_server(int(os.getenv("PORT", "8080")))

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
