"""
Configuration loader with YAML and environment variable overrides.

FIXED 2026-09-23: dataclass defaults now match config.yaml. They previously
said htf_timeframe="4h" and fixed_risk_percent=1.0 while the YAML said "1h"
and 0.5 — so a missing or malformed config.yaml silently doubled your risk per
trade and changed the dealing-range timeframe, with no warning.
"""
import os
import logging
from dataclasses import dataclass, field
from typing import List
import yaml

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    smt_benchmark: str = "ETH/USDT"
    ltf_timeframe: str = "5m"
    htf_timeframe: str = "1h"        # FIXED: was "4h"
    scan_interval_seconds: int = 60
    min_risk_reward: float = 2.5
    fixed_risk_percent: float = 0.5  # FIXED: was 1.0

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    @classmethod
    def load(cls, path: str = "config.yaml") -> "AppConfig":
        cfg = cls()
        if not os.path.exists(path):
            logger.warning(
                f"{path} not found - running on built-in defaults "
                f"(risk {cfg.fixed_risk_percent}%, HTF {cfg.htf_timeframe})."
            )
            return cfg

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if "symbols" in data:
            cfg.symbols = data["symbols"]
        if "smt_benchmark" in data:
            cfg.smt_benchmark = data["smt_benchmark"]
        if "ltf_timeframe" in data:
            cfg.ltf_timeframe = data["ltf_timeframe"]
        if "htf_timeframe" in data:
            cfg.htf_timeframe = data["htf_timeframe"]
        if "scan_interval_seconds" in data:
            cfg.scan_interval_seconds = int(data["scan_interval_seconds"])
        if "min_risk_reward" in data:
            cfg.min_risk_reward = float(data["min_risk_reward"])
        if "fixed_risk_percent" in data:
            cfg.fixed_risk_percent = float(data["fixed_risk_percent"])
        if "telegram_bot_token" in data:
            cfg.telegram_bot_token = data["telegram_bot_token"]
        if "telegram_chat_id" in data:
            cfg.telegram_chat_id = data["telegram_chat_id"]
        if "discord_webhook_url" in data:
            cfg.discord_webhook_url = data["discord_webhook_url"]

        cfg.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", cfg.telegram_bot_token)
        cfg.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", cfg.telegram_chat_id)
        cfg.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", cfg.discord_webhook_url)

        return cfg
