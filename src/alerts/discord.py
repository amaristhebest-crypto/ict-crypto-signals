"""
Discord Webhook Notifier for ICT Crypto Signals.
"""
import requests
import logging
from src.core.models import ICTSignal, Direction

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_signal(self, signal: ICTSignal) -> bool:
        if not self.webhook_url or "YOUR_" in self.webhook_url:
            return False

        color = 0x10B981 if signal.direction == Direction.BULLISH else 0xEF4444
        direction_str = "🟢 LONG" if signal.direction == Direction.BULLISH else "🔴 SHORT"

        embed = {
            "title": f"⚡ ICT Signal: {signal.symbol} — {direction_str}",
            "description": f"**Setup:** {signal.setup_name}\n**Session:** {signal.session_name}",
            "color": color,
            "fields": [
                {"name": "Limit Entry", "value": f"${signal.entry_price:,.2f}", "inline": True},
                {"name": "Stop Loss", "value": f"${signal.stop_loss:,.2f}", "inline": True},
                {"name": "R:R Ratio", "value": f"1:{signal.risk_reward_ratio:.2f}R", "inline": True},
                {"name": "Target 1 (50% Off)", "value": f"${signal.target_1:,.2f}", "inline": True},
                {"name": "Target 2 (Runner)", "value": f"${signal.target_2:,.2f}", "inline": True},
                {"name": "Target 3 (Macro DOL)", "value": f"${signal.target_3:,.2f}", "inline": True},
                {
                    "name": "Confluences",
                    "value": "\n".join([f"• {c}" for c in signal.confluence_factors]),
                    "inline": False,
                },
                {"name": "Invalidation", "value": signal.invalidation_notes, "inline": False},
            ],
            "footer": {"text": "ICT Institutional Price Delivery Algorithm Engine"},
            "timestamp": signal.timestamp.isoformat(),
        }

        try:
            resp = requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to send Discord webhook: {e}")
            return False
