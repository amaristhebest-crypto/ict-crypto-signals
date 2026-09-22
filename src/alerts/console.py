"""
Terminal Console Formatter for ICT Signals with Ultra-Simple 3-Point Bracket Order.
"""
from src.core.models import ICTSignal, Direction
from src.core.sessions import SessionDetector


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


class ConsoleNotifier:
    @staticmethod
    def print_signal(signal: ICTSignal):
        dir_color = "\033[92m" if signal.direction == Direction.BULLISH else "\033[91m"
        reset = "\033[0m"
        bold = "\033[1m"
        cyan = "\033[96m"
        green = "\033[92m"
        red = "\033[91m"

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")
        tv_link = get_tv_link(signal.symbol)
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        print("\n" + "=" * 60)
        print(f"{bold}{dir_color}⚡ ICT SIGNAL: {signal.symbol} ({signal.direction.value}) ⚡{reset}")
        print("=" * 60)
        print(f"Time (India): {ist_time} ({ny_time} NY)")
        print(f"Session     : {signal.session_name}")
        print(f"Live Chart  : {tv_link}")

        print("\n" + "-" * 60)
        print(f"{bold}🎯 SIMPLE 3-STEP BRACKET ORDER (COPY & PASTE):{reset}")
        print("-" * 60)
        print(f"  1️⃣  {bold}ENTRY{reset}       : {bold}{cyan}${signal.entry_price:,.2f}{reset}  ({order_type})")
        print(f"  2️⃣  {bold}STOP LOSS{reset}   : {bold}{red}${signal.stop_loss:,.2f}{reset}")
        print(f"  3️⃣  {bold}TAKE PROFIT{reset} : {bold}{green}${signal.target_2:,.2f}{reset}  (1 : {signal.risk_reward_ratio:.1f} R:R)")
        print("-" * 60)
        print(f"  💡 {bold}Optional Breakeven:{reset} Once price hits ${signal.target_1:,.2f}, drag stop to ${signal.entry_price:,.2f}")
        print("=" * 60 + "\n")
