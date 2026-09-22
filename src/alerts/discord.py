"""
Discord Webhook Notifier Tailored Specifically for MFFU 50K Account Trading.
"""
import requests
import logging
from src.core.models import ICTSignal, Direction
from src.core.sessions import SessionDetector
from src.core.mffu import MFFUHelper

logger = logging.getLogger(__name__)


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
        m = MFFUHelper.calculate_trade_metrics(
            signal.symbol,
            signal.entry_price,
            signal.stop_loss,
            signal.target_2,
            quantity=2,
        )

        order_box = (
            f"**Search Ticker:** `{m['mffu_ticker']}` ({m['contract_name']})\n"
            f"**Quantity:** `2 Micro Contracts`\n\n"
            f"**1️⃣ ENTRY:** `${signal.entry_price:,.2f}` ({order_type})\n"
            f"**2️⃣ STOP LOSS:** `${signal.stop_loss:,.2f}` (Risk: ${m['dollar_risk']:,.2f})\n"
            f"**3️⃣ TAKE PROFIT:** `${signal.target_2:,.2f}` (Reward: +${m['dollar_profit']:,.2f} | 1:{signal.risk_reward_ratio:.1f} R:R)\n\n"
            f"💡 *Move SL to Breakeven (${signal.entry_price:,.2f}) after first push (${signal.target_1:,.2f})*"
        )

        risk_box = (
            f"• **Risk on 2 Micros:** `${m['dollar_risk']:,.2f}` ({m['cushion_pct']:.1f}% of $2,000 drawdown)\n"
            f"• **EOD Invalidation Floor:** `$48,000.00`\n"
            f"• **50% Daily Profit Cap:** `$1,500.00`"
        )

        embed = {
            "title": f"⚡ MFFU 50K Signal: {m['mffu_ticker']} — {direction_str}",
            "description": f"**Time (India):** {ist_time}\n**Session:** {signal.session_name}\n[📈 Open Chart on TradingView]({m['tv_url']})",
            "color": color,
            "fields": [
                {
                    "name": "📋 Tradovate / TradingView Order (Copy & Paste)",
                    "value": order_box,
                    "inline": False,
                },
                {
                    "name": "💰 50K Account Risk Parameters",
                    "value": risk_box,
                    "inline": False,
                },
            ],
            "footer": {
                "text": "My Funded Futures (MFFU) Execution Engine • 24/7 Cloud",
            },
        }

        try:
            resp = requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)
            return resp.status_code == 204
        except Exception as e:
            logger.error(f"Failed to post Discord alert: {e}")
            return False
