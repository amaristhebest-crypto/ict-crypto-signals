"""
Terminal Console Formatter for ICT Signals with Complete Step-by-Step Execution Plan.
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
        yellow = "\033[93m"
        green = "\033[92m"
        red = "\033[91m"

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")

        tv_link = get_tv_link(signal.symbol)
        risk_per_unit = abs(signal.entry_price - signal.stop_loss)
        action_word = "BUY / LONG" if signal.direction == Direction.BULLISH else "SELL / SHORT"
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        print("\n" + "=" * 76)
        print(f"{bold}{dir_color}⚡ [ICT AUTOMATED SIGNAL DETECTED] {signal.symbol} ({signal.timeframe}) ⚡{reset}")
        print("=" * 76)
        print(f"Setup Model : {signal.setup_name}")
        print(f"Session     : {signal.session_name}")
        print(f"Time (India): {bold}{cyan}{ist_time}{reset} ({ny_time} NY)")
        print(f"Direction   : {bold}{dir_color}{action_word}{reset}")
        print(f"Risk/Reward : {bold}{green}1 : {signal.risk_reward_ratio:.2f} R{reset}")
        print(f"Live Chart  : {tv_link}")

        print("\n" + "-" * 76)
        print(f"{bold}📋 EXACT STEP-BY-STEP TRADE EXECUTION PLAN (NO MANUAL MATH REQUIRED):{reset}")
        print("-" * 76)
        print(f"  👉 {bold}STEP 1 (ENTRY):{reset} Place {cyan}{order_type}{reset} at {bold}{cyan}${signal.entry_price:,.2f}{reset} (FVG 50% CE)")
        print(f"  👉 {bold}STEP 2 (STOP LOSS):{reset} Hard Stop at {bold}{red}${signal.stop_loss:,.2f}{reset} (Risk distance: ${risk_per_unit:,.2f})")
        print(f"  👉 {bold}STEP 3 (TP 1):{reset} Target at {bold}{yellow}${signal.target_1:,.2f}{reset}")
        print(f"     ↳ {bold}ACTION:{reset} Close {bold}50%{reset} position & IMMEDIATELY move Stop Loss to Breakeven ({bold}${signal.entry_price:,.2f}{reset})")
        print(f"     ↳ {green}Result: Trade is now 100% RISK-FREE with locked-in profit!{reset}")
        print(f"  👉 {bold}STEP 4 (TP 2):{reset} Target at {bold}{green}${signal.target_2:,.2f}{reset}")
        print(f"     ↳ {bold}ACTION:{reset} Close {bold}25%{reset} position (75% total secured). Symmetrical OTE -0.27.")
        print(f"  👉 {bold}STEP 5 (TP 3):{reset} Target at {bold}{green}${signal.target_3:,.2f}{reset}")
        print(f"     ↳ {bold}ACTION:{reset} Close final {bold}25% runner{reset} at Macro Draw on Liquidity.")

        # Sizing table based on standard 1% account risk
        if risk_per_unit > 0:
            print("\n" + "-" * 76)
            print(f"{bold}💰 RECOMMENDED POSITION SIZING (Fixed 1% Account Risk):{reset}")
            print("-" * 76)
            for acc in [1000, 5000, 10000, 25000]:
                risk_cash = acc * 0.01
                units = risk_cash / risk_per_unit
                print(f"  • ${acc:,} Account (1% Risk = ${risk_cash:.2f}): Size = {bold}{units:.4f}{reset} units / contracts")

        print("\n" + "-" * 76)
        print("🧠 Institutional Confluences:")
        for c in signal.confluence_factors:
            print(f"  ✔ {c}")
        print(f"\n⚠️ Invalidation: {signal.invalidation_notes}")
        print("=" * 76 + "\n")
