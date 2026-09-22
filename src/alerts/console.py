"""
Terminal Console Formatter for ICT Signals.
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

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")

        tv_link = get_tv_link(signal.symbol)

        print("\n" + "=" * 70)
        print(f"{bold}{dir_color}⚡ [ICT AUTOMATED SIGNAL DETECTED] {signal.symbol} ({signal.timeframe}) ⚡{reset}")
        print("=" * 70)
        print(f"Setup Model : {signal.setup_name}")
        print(f"Session     : {signal.session_name}")
        print(f"Time (India): {bold}{cyan}{ist_time}{reset} ({ny_time} NY)")
        print(f"Direction   : {bold}{dir_color}{signal.direction.value}{reset}")
        print(f"Limit Entry : {cyan}${signal.entry_price:,.2f}{reset}")
        print(f"Stop Loss   : \033[91m${signal.stop_loss:,.2f}{reset}")
        print(f"Target 1    : ${signal.target_1:,.2f} (50% Off / Move Stop to Breakeven)")
        print(f"Target 2    : ${signal.target_2:,.2f} (Liquidity Pool / OTE -0.27)")
        print(f"Target 3    : ${signal.target_3:,.2f} (HTF DOL / OTE -0.62)")
        print(f"Risk/Reward : {bold}1 : {signal.risk_reward_ratio:.2f} R{reset}")
        print(f"Live Chart  : {tv_link}")
        print("\nConfluences:")
        for c in signal.confluence_factors:
            print(f"  ✔ {c}")
        print(f"\nInvalidation: {signal.invalidation_notes}")
        print("=" * 70 + "\n")
