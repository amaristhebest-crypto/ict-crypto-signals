"""
Discord Webhook Notifier for ICT Signals with Complete Trade Management Automation.
"""
import requests
import logging
from src.core.models import ICTSignal, Direction
from src.core.sessions import SessionDetector

logger = logging.getLogger(__name__)


def get_tv_link(symbol: str) -> str:
    clean = symbol.upper().replace("/", "").replace(":USDT", "USDT")
    if clean in ("GOLD", "GC=F", "XAUUSD"):
        return "https://www.tradingview.com/chart/?symbol=TVC:GOLD"
    if clean in ("SILVER", "SI=F", "XAGUSD"):
        return "https://www.tradingview.com/chart/?symbol=TVC:SILVER"
    if clean in ("CRUDE", "CL=F", "OIL", "WTI"):
        return "https://www.tradingview.com/chart/?symbol=TVC:USOIL"
    if clean in ("NQ", "NQZ2026", "NQZ26", "NQ1!", "NQ=F", "NASDAQ"):
        return "https://www.tradingview.com/chart/?symbol=CME_MINI:NQ1!"
    if clean in ("ES", "ESZ2026", "ESZ26", "ES1!", "ES=F", "SP500"):
        return "https://www.tradingview.com/chart/?symbol=CME_MINI:ES1!"
    return f"https://www.tradingview.com/chart/?symbol=OKX:{clean}"


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_signal(self, signal: ICTSignal) -> bool:
        if not self.webhook_url or "YOUR_" in self.webhook_url:
            return False

        color = 0x10B981 if signal.direction == Direction.BULLISH else 0xEF4444
        direction_str = "🟢 LONG / BUY" if signal.direction == Direction.BULLISH else "🔴 SHORT / SELL"
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")
        tv_link = get_tv_link(signal.symbol)
        risk_per_unit = abs(signal.entry_price - signal.stop_loss)

        trade_plan = (
            f"**1️⃣ ENTRY:** `{order_type}` at `${signal.entry_price:,.2f}` (FVG 50% CE)\n"
            f"**2️⃣ STOP LOSS:** `${signal.stop_loss:,.2f}` (Risk: ${risk_per_unit:,.2f})\n"
            f"**3️⃣ TP 1:** `${signal.target_1:,.2f}` ➔ **Close 50% & Move SL to Breakeven (${signal.entry_price:,.2f})**\n"
            f"**4️⃣ TP 2:** `${signal.target_2:,.2f}` ➔ Close 25% position (OTE -0.27)\n"
            f"**5️⃣ TP 3:** `${signal.target_3:,.2f}` ➔ Close final 25% runner (Macro HTF DOL)\n"
            f"**⚖️ Risk/Reward:** `1 : {signal.risk_reward_ratio:.2f} R`"
        )

        embed = {
            "title": f"⚡ ICT Signal: {signal.symbol} — {direction_str}",
            "description": f"**Setup:** {signal.setup_name}\n**Session:** {signal.session_name}\n**Time (India):** {ist_time} ({ny_time} NY)\n[📈 Open TradingView Chart]({tv_link})",
            "color": color,
            "fields": [
                {
                    "name": "📋 Exact Step-by-Step Trade Execution Plan",
                    "value": trade_plan,
                    "inline": False,
                },
                {
                    "name": "🧠 Institutional Footprints & Confluences",
                    "value": "\n".join([f"• {c}" for c in signal.confluence_factors]),
                    "inline": False,
                },
                {
                    "name": "⚠️ Invalidation Rule",
                    "value": signal.invalidation_notes,
                    "inline": False,
                },
            ],
            "footer": {
                "text": "ICT 2022 Mentorship Automated Engine • 24/7 Cloud",
            },
        }

        try:
            resp = requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)
            return resp.status_code == 204
        except Exception as e:
            logger.error(f"Failed to post Discord alert: {e}")
            return False
