"""
Telegram Alert Notifier Tailored Specifically for MFFU 50K Account Trading.
"""
import requests
import logging
from src.core.models import ICTSignal, Direction
from src.core.sessions import SessionDetector
from src.core.mffu import MFFUHelper

logger = logging.getLogger(__name__)


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
        m = MFFUHelper.calculate_trade_metrics(
            signal.symbol,
            signal.entry_price,
            signal.stop_loss,
            signal.target_2,
            quantity=2,
        )

        message = (
            f"⚡ *MFFU 50K TRADING SIGNAL: {m['mffu_ticker']}* ⚡\n\n"
            f"{icon} *Action:* *{action}*\n"
            f"🕒 *Time (India):* `{ist_time}`\n"
            f"🏛 *Session:* `{signal.session_name}`\n\n"
            f"📋 *TRADOVATE / TRADINGVIEW SETUP:*\n"
            f"  👉 *Platform Ticker:* `{m['mffu_ticker']}` ({m['contract_name']})\n"
            f"  👉 *Order Type:* `{order_type}`\n"
            f"  👉 *Quantity:* `2 Micro Contracts`\n\n"
            f"🎯 *3-POINT BRACKET ORDER (COPY & PASTE):*\n"
            f"1️⃣ *ENTRY:* `${signal.entry_price:,.2f}` (FVG 50% CE)\n"
            f"2️⃣ *STOP LOSS:* `${signal.stop_loss:,.2f}`\n"
            f"3️⃣ *TAKE PROFIT:* `${signal.target_2:,.2f}` (1 : {signal.risk_reward_ratio:.1f} R:R)\n\n"
            f"💰 *MFFU 50K RISK CHECK:*\n"
            f"  • *Dollar Risk (2 Micros):* `${m['dollar_risk']:,.2f}` (Only {m['cushion_pct']:.1f}% of $2k cushion)\n"
            f"  • *Dollar Reward (2 Micros):* `+${m['dollar_profit']:,.2f}`\n"
            f"  • *Drawdown Floor:* `$48,000.00` EOD\n"
            f"  • *50% Daily Profit Cap:* `$1,500.00`\n\n"
            f"💡 *Rule:* Once price hits `${signal.target_1:,.2f}`, drag Stop Loss to `${signal.entry_price:,.2f}`.\n"
            f"📈 [Open Chart on TradingView]({m['tv_url']})"
        )

        try:
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}
            resp = requests.post(self.api_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
