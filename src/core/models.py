"""
Core data models representing ICT / SMC concepts.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class Direction(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class ArrayType(Enum):
    FVG = "FAIR_VALUE_GAP"
    ORDER_BLOCK = "ORDER_BLOCK"
    BREAKER_BLOCK = "BREAKER_BLOCK"
    MITIGATION_BLOCK = "MITIGATION_BLOCK"
    REJECTION_BLOCK = "REJECTION_BLOCK"
    LIQUIDITY_VOID = "LIQUIDITY_VOID"


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)

    @property
    def body_height(self) -> float:
        return abs(self.close - self.open)

    @property
    def total_range(self) -> float:
        return self.high - self.low


@dataclass
class SwingPoint:
    index: int
    timestamp: datetime
    price: float
    is_high: bool  # True for STH/ITH, False for STL/ITL
    is_intermediate: bool = False
    swept: bool = False


@dataclass
class FairValueGap:
    top: float
    bottom: float
    consequent_encroachment: float  # 50% midpoint
    direction: Direction
    candle_index: int
    timestamp: datetime
    mitigated: bool = False
    mitigated_at: Optional[datetime] = None


@dataclass
class OrderBlock:
    high: float
    low: float
    mean_threshold: float  # 50% midpoint of candle body
    direction: Direction
    candle_index: int
    timestamp: datetime
    mitigated: bool = False


@dataclass
class BreakerBlock:
    high: float
    low: float
    mean_threshold: float
    direction: Direction
    candle_index: int
    timestamp: datetime


@dataclass
class SMTResult:
    detected: bool
    direction: Optional[Direction] = None
    asset_a: str = ""
    asset_a_sweep: str = ""  # e.g., "Lower Low"
    asset_b: str = ""
    asset_b_sweep: str = ""  # e.g., "Higher Low"
    timestamp: Optional[datetime] = None
    description: str = ""


@dataclass
class ICTSignal:
    symbol: str
    timeframe: str
    direction: Direction
    setup_name: str
    session_name: str
    timestamp: datetime
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    target_3: float
    risk_reward_ratio: float
    invalidation_notes: str
    confluence_factors: List[str] = field(default_factory=list)
