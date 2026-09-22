"""
Terminal Console Formatter for ICT Signals Tailored Specifically for MFFU 50K Trading.
"""
from src.core.models import ICTSignal, Direction
from src.core.sessions import SessionDetector
from src.core.mffu import MFFUHelper


class ConsoleNotifier:
    @staticmethod
    def print_signal(signal: ICTSignal):
        dir_color = "\033[92m" if signal.direction == Direction.BULLISH else "\033[91m"
        reset = "\033[0m"
        bold = "\033[1m"
        cyan = "\033[96m"
        green = "\033[92m"
        red = "\033[91m"
        yellow = "\033[93m"

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p EDT")
        action_word = "BUY / LONG" if signal.direction == Direction.BULLISH else "SELL / SHORT"
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        m = MFFUHelper.calculate_trade_metrics(
            signal.symbol,
            signal.entry_price,
            signal.stop_loss,
            signal.target_2,
            quantity=2,
        )

        print("\n" + "=" * 70)
        print(f"{bold}{dir_color}⚡ [MFFU 50K TRADING SIGNAL] {m['mffu_ticker']} ({signal.direction.value}) ⚡{reset}")
        print("=" * 70)
        print(f"Time (India): {bold}{cyan}{ist_time}{reset} ({ny_time} NY)")
        print(f"Session     : {signal.session_name}")
        print(f"Live Chart  : {m['tv_url']}")

        print("\n" + "-" * 70)
        print(f"{bold}📋 MFFU TRADOVATE / TRADINGVIEW ORDER INSTRUCTIONS:{reset}")
        print("-" * 70)
        print(f"  👉 {bold}Search Ticker   :{reset} {bold}{yellow}{m['mffu_ticker']}{reset} ({m['contract_name']})")
        print(f"  👉 {bold}Order Type      :{reset} {bold}{cyan}{order_type}{reset}")
        print(f"  👉 {bold}Order Quantity  :{reset} {bold}2 Micro Contracts{reset}")

        print("\n" + "-" * 70)
        print(f"{bold}🎯 3-POINT BRACKET ORDER (COPY & PASTE INTO TRADOVATE):{reset}")
        print("-" * 70)
        print(f"  1️⃣  {bold}ENTRY PRICE    :{reset} {bold}{cyan}${signal.entry_price:,.2f}{reset}  (Limit Entry at FVG 50% CE)")
        print(f"  2️⃣  {bold}STOP LOSS      :{reset} {bold}{red}${signal.stop_loss:,.2f}{reset}  (Distance: {m['risk_points']:,.2f} pts)")
        print(f"  3️⃣  {bold}TAKE PROFIT    :{reset} {bold}{green}${signal.target_2:,.2f}{reset}  (1 : {signal.risk_reward_ratio:.1f} R:R)")
        print("-" * 70)
        print(f"  💡 {bold}Breakeven Rule :{reset} Once price hits ${signal.target_1:,.2f}, drag Stop Loss to ${signal.entry_price:,.2f} (100% Risk-Free)")

        print("\n" + "-" * 70)
        print(f"{bold}💰 MFFU 50K ACCOUNT RISK MANAGEMENT (ZERO CONFUSION):{reset}")
        print("-" * 70)
        print(f"  • Dollar Risk on 2 Micros   : {bold}{red}${m['dollar_risk']:,.2f}{reset} (Only {m['cushion_pct']:.1f}% of your $2,000 drawdown cushion)")
        print(f"  • Dollar Profit on 2 Micros : {bold}{green}+${m['dollar_profit']:,.2f}{reset}")
        print(f"  • Invalidation Floor        : $48,000.00 (End-of-Day EOD)")
        print(f"  • 50% Consistency Rule Cap  : Do not exceed +$1,500.00 profit today")
        print("=" * 70 + "\n")
