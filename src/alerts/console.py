"""
Terminal formatter for ICT signals, tailored to MFFU 50K execution.

FIXED 2026-09-23:
  * Hardcoded "EDT" replaced with %Z (correct year-round; the literal was
    wrong from 1 November to 8 March).
  * Non-tradeable instruments now print a warning instead of a bracket order.
  * R:R is now labelled as being measured against the printed take profit,
    because it finally is.
"""
from src.core.models import ICTSignal, Direction
from src.core.sessions import SessionDetector
from src.core.mffu import MFFUHelper


class ConsoleNotifier:
    @staticmethod
    def print_signal(signal: ICTSignal):
        dir_color = "\033[92m" if signal.direction == Direction.BULLISH else "\033[91m"
        reset, bold = "\033[0m", "\033[1m"
        cyan, green, red, yellow = "\033[96m", "\033[92m", "\033[91m", "\033[93m"

        ist_time = SessionDetector.to_ist_time(signal.timestamp).strftime("%d %b %Y, %I:%M %p IST")
        ny_time = SessionDetector.to_ny_time(signal.timestamp).strftime("%I:%M %p %Z")
        order_type = "LIMIT BUY" if signal.direction == Direction.BULLISH else "LIMIT SELL"

        m = MFFUHelper.calculate_trade_metrics(
            signal.symbol, signal.entry_price, signal.stop_loss, signal.target_2, quantity=2,
        )

        print("\n" + "=" * 70)
        print(f"{bold}{dir_color}[MFFU 50K SIGNAL] {m['mffu_ticker']} ({signal.direction.value}){reset}")
        print("=" * 70)
        print(f"Time (India): {bold}{cyan}{ist_time}{reset} ({ny_time} NY)")
        print(f"Session     : {signal.session_name}")
        if m["tv_url"]:
            print(f"Live Chart  : {m['tv_url']}")

        if not m["tradeable"]:
            print("\n" + "-" * 70)
            print(f"{bold}{red}NOT TRADEABLE ON MFFU{reset}")
            print("-" * 70)
            print(f"  No CME futures contract exists for {signal.symbol}.")
            print("  This is an analysis / SMT reference only. Do not place an order.")
            print("=" * 70 + "\n")
            return

        print("\n" + "-" * 70)
        print(f"{bold}ORDER INSTRUCTIONS:{reset}")
        print("-" * 70)
        print(f"  Ticker   : {bold}{yellow}{m['mffu_ticker']}{reset} ({m['contract_name']})")
        print(f"  Type     : {bold}{cyan}{order_type}{reset}")
        print(f"  Quantity : {bold}2 Micro Contracts{reset}")

        print("\n" + "-" * 70)
        print(f"{bold}3-POINT BRACKET ORDER:{reset}")
        print("-" * 70)
        print(f"  1. ENTRY       : {bold}{cyan}${signal.entry_price:,.2f}{reset}   (FVG 50% CE)")
        print(f"  2. STOP LOSS   : {bold}{red}${signal.stop_loss:,.2f}{reset}   ({m['risk_points']:,.2f} pts)")
        print(f"  3. TAKE PROFIT : {bold}{green}${signal.target_2:,.2f}{reset}   (1 : {signal.risk_reward_ratio:.2f} R:R)")
        print("-" * 70)
        print(f"  R:R is measured against the take profit above, not a further target.")
        print(f"  Reference only - T1 {signal.target_1:,.2f} / T3 {signal.target_3:,.2f}")

        print("\n" + "-" * 70)
        print(f"{bold}RISK CHECK (2 micros):{reset}")
        print("-" * 70)
        print(f"  Dollar risk   : {bold}{red}${m['dollar_risk']:,.2f}{reset}")
        print(f"  Dollar profit : {bold}{green}+${m['dollar_profit']:,.2f}{reset}")
        print(f"  EOD floor     : $48,000.00   |   Daily cap: $1,500.00")

        print("\n" + "-" * 70)
        print("Confluences:")
        for c in signal.confluence_factors:
            print(f"  - {c}")
        print(f"\nInvalidation: {signal.invalidation_notes}")
        print("=" * 70 + "\n")
