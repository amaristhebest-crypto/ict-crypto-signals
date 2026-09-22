"""
Discord Webhook Notifier for ICT Signals with Ultra-Simple 3-Point Bracket Order.
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
        direction_str = "🟢 BUY / LONG" if signal.direction == Direction.BULLISH else "🔴 SELL / SHORT"
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        tv_link = get_tv_link(signal.symbol)

        trade_plan = (
            f"**1️⃣ ENTRY:** `${signal.entry_price:,.2f}` ({order_type})\n"
            f"**2️⃣ STOP LOSS:** `${signal.stop_loss:,.2f}`\n"
            f"**3️⃣ TAKE PROFIT:** `${signal.target_2:,.2f}` (1 : {signal.risk_reward_ratio:.1f} R:R)\n\n"
            f"💡 *Optional Breakeven:* Move SL to `${signal.entry_price:,.2f}` once price hits `${signal.target_1:,.2f}`."
        )

        embed = {
            "title": f"⚡ ICT Signal: {signal.symbol} — {direction_str}",
            "description": f"**Time (India):** {ist_time}\n**Session:** {signal.session_name}\n[📈 Open TradingView Chart]({tv_link})",
            "color": color,
            "fields": [
                {
                    "name": "🎯 Simple 3-Step Bracket Order",
                    "value": trade_plan,
                    "inline": False,
                }
            ],
            "footer": {
                "text": "ICT Automated Signal Engine",
            },
        }

        try:
            resp = requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)
            return resp.status_code == 204
        except Exception as e:
            logger.error(f"Failed to post Discord alert: {e}")
            return False
