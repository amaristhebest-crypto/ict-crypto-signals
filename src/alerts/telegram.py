"""
Telegram Alert Notifier for ICT Signals with Ultra-Simple 3-Point Bracket Order.
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


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_signal(self, signal: ICTSignal) -> bool:
        if not self.bot_token or not self.chat_id or "YOUR_" in self.bot_token:
            return False

        icon = "🟢" if signal.direction == Direction.BULLISH else "🔴"
        action = "BUY / LONG" if signal.direction == Direction.BULLISH else "SELL / SHORT"
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        tv_link = get_tv_link(signal.symbol)

        message = (
            f"⚡ *ICT SIGNAL: {signal.symbol}* ⚡\n\n"
            f"{icon} *Action:* *{action}*\n"
            f"🕒 *Time:* `{ist_time}`\n"
            f"📈 [Open Chart]({tv_link})\n\n"
            f"🎯 *SIMPLE 3-STEP BRACKET ORDER:*\n"
            f"1️⃣ *ENTRY:* `${signal.entry_price:,.2f}` ({order_type})\n"
            f"2️⃣ *STOP LOSS:* `${signal.stop_loss:,.2f}`\n"
            f"3️⃣ *TAKE PROFIT:* `${signal.target_2:,.2f}` (1:{signal.risk_reward_ratio:.1f} R:R)\n\n"
            f"💡 *Tip:* Move Stop Loss to Breakeven (${signal.entry_price:,.2f}) after first push (${signal.target_1:,.2f})."
        )

        try:
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}
            resp = requests.post(self.api_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
