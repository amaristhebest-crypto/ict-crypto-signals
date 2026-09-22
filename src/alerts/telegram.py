"""
Telegram Alert Notifier for ICT Signals with Complete Trade Management Automation.
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
            logger.info("Telegram credentials not configured. Skipping Telegram dispatch.")
            return False

        icon = "🟢" if signal.direction == Direction.BULLISH else "🔴"
        direction_str = "LONG / BUY" if signal.direction == Direction.BULLISH else "SHORT / SELL"
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        confluence_list = "\n".join([f"  • {c}" for c in signal.confluence_factors])
        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")
        tv_link = get_tv_link(signal.symbol)
        risk_per_unit = abs(signal.entry_price - signal.stop_loss)

        # Sizing table for 1% risk
        size_txt = ""
        if risk_per_unit > 0:
            size_txt = (
                f"\n💰 *RECOMMENDED SIZING (1% Risk):*\n"
                f"  • $1,000 Acc ($10 risk): `{(10/risk_per_unit):.4f}` units\n"
                f"  • $5,000 Acc ($50 risk): `{(50/risk_per_unit):.4f}` units\n"
                f"  • $10,000 Acc ($100 risk): `{(100/risk_per_unit):.4f}` units\n"
            )

        message = (
            f"⚡ *ICT INSTITUTIONAL SIGNAL* ⚡\n\n"
            f"{icon} *Asset:* `{signal.symbol}` ({signal.timeframe})\n"
            f"🎯 *Direction:* *{direction_str}*\n"
            f"🏛 *Setup:* `{signal.setup_name}`\n"
            f"🕒 *Session:* `{signal.session_name}`\n"
            f"🇮🇳 *Time (India):* `{ist_time}` ({ny_time} NY)\n"
            f"⚖️ *Risk/Reward:* `1 : {signal.risk_reward_ratio:.2f} R`\n\n"
            f"📋 *EXACT STEP-BY-STEP TRADE EXECUTION:*\n"
            f"  1️⃣ *ENTRY:* Set `{order_type}` at `${signal.entry_price:,.2f}` (FVG 50% CE)\n"
            f"  2️⃣ *STOP LOSS:* Hard Stop at `${signal.stop_loss:,.2f}` (Risk: ${risk_per_unit:,.2f})\n"
            f"  3️⃣ *TP 1:* `${signal.target_1:,.2f}`\n"
            f"     ↳ *Rule:* Close *50% position* & move Stop Loss to *Breakeven* (`${signal.entry_price:,.2f}`).\n"
            f"     ↳ *Result:* Guaranteed profit locked; trade is 100% risk-free!\n"
            f"  4️⃣ *TP 2:* `${signal.target_2:,.2f}`\n"
            f"     ↳ *Rule:* Close *25% position* (75% total secured). OTE -0.27.\n"
            f"  5️⃣ *TP 3:* `${signal.target_3:,.2f}`\n"
            f"     ↳ *Rule:* Close final *25% runner* at Macro HTF DOL.\n"
            f"{size_txt}\n"
            f"📈 [Open TradingView Chart]({tv_link})\n\n"
            f"🧠 *CONFLUENCES:*\n"
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
