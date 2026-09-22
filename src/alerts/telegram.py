"""
Telegram Alert Notifier for ICT Crypto Signals.
"""
import requests
import logging
from src.core.models import ICTSignal, Direction

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
            logger.info("Telegram credentials not configured. Skipping Telegram dispatch.")
            return False

        icon = "🟢" if signal.direction == Direction.BULLISH else "🔴"
        direction_str = "LONG / BUY" if signal.direction == Direction.BULLISH else "SHORT / SELL"

        confluence_list = "\n".join([f"  • {c}" for c in signal.confluence_factors])

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")
        tv_link = get_tv_link(signal.symbol)

        message = (
            f"⚡ *ICT INSTITUTIONAL CRYPTO SIGNAL* ⚡\n\n"
            f"{icon} *Asset:* `{signal.symbol}` ({signal.timeframe})\n"
            f"🎯 *Direction:* *{direction_str}*\n"
            f"🏛 *Setup:* `{signal.setup_name}`\n"
            f"🕒 *Session:* `{signal.session_name}`\n"
            f"🇮🇳 *Time (India):* `{ist_time}` ({ny_time} NY)\n\n"
            f"📊 *TRADE PARAMETERS:*\n"
            f"  • *Limit Entry:* `${signal.entry_price:,.2f}`\n"
            f"  • *Stop Loss:* `${signal.stop_loss:,.2f}`\n"
            f"  • *Target 1 (50% Off / SL->BE):* `${signal.target_1:,.2f}`\n"
            f"  • *Target 2 (Runner TP):* `${signal.target_2:,.2f}`\n"
            f"  • *Target 3 (Macro DOL):* `${signal.target_3:,.2f}`\n"
            f"  • *Risk/Reward Ratio:* `1:{signal.risk_reward_ratio:.2f}R`\n\n"
            f"📈 [Open TradingView Live Chart]({tv_link})\n\n"
            f"🧠 *CONFLUENCES & INSTITUTIONAL FOOTPRINTS:*\n"
            f"{confluence_list}\n\n"
            f"⚠️ *INVALIDATION:* {signal.invalidation_notes}\n"
        )

        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            resp = requests.post(self.api_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
