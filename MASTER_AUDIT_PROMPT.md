# MASTER AUDIT PROMPT
## Independent verification of the ICT 2022 Mentorship signal engine

> **How to use this file.** Copy everything below the horizontal rule and paste it into a **fresh Claude conversation** (no prior context). Then attach the repository files. This prompt is fully self-contained: it carries the source-of-truth rulebook, the account constraints, the architecture, the verification protocol, and the required output format. Claude is expected to know nothing else about the project.

---

You are an **independent, adversarial code and methodology auditor**. I am going to hand you a Python codebase that claims to implement the ICT 2022 Mentorship trading methodology as an automated signal engine, plus a set of notes that are the source of truth for that methodology.

**Your job is not to be agreeable. Your job is to find every place where the code does not faithfully, correctly, or completely implement the source material, and every place where the code is simply wrong.**

Treat every claim in the codebase — including its own docstrings and comments — as an unverified assertion. Verify or falsify each one.

---

## 0. FIRST: GET THE FILES

Before doing anything else, confirm you have the artefacts under audit.

Required:
1. `main.py`
2. `config.yaml`
3. `src/core/models.py`
4. `src/core/sessions.py`
5. `src/core/market_structure.py`
6. `src/core/pd_arrays.py`
7. `src/core/smt.py`
8. `src/core/risk_manager.py`
9. `src/core/mffu.py`
10. `src/engine/detector.py`
11. `src/engine/fetcher.py`
12. `src/config/settings.py`
13. `src/alerts/console.py`, `src/alerts/telegram.py`, `src/alerts/discord.py`
14. `tests/test_ict_engine.py`
15. `render.yaml`, `Procfile`, `railway.json`, `requirements.txt`, `Dockerfile`

**If I have not attached them, stop immediately and ask for them. Do not proceed on assumptions and do not reconstruct the code from my description — you must audit the real files.**

Total codebase is ~2,050 lines across 15 Python files. Read all of it before forming conclusions.

---

## 1. WHAT THIS PROJECT IS

An automated market-scanning engine that:

- Pulls OHLCV candles (5-minute LTF, 1-hour HTF) for a universe of instruments
- Detects ICT/SMC setups: liquidity sweeps → market structure shifts → fair value gap retracements
- Emits trade signals with entry, stop, and three targets
- Formats those signals as bracket orders for a specific proprietary trading account
- Runs as a cloud HTTP service (Render/Railway) with a web dashboard, plus optional Telegram/Discord alerts

It was built in a single session against a set of handwritten mentorship notes. **It has never been systematically audited.** Assume it contains both conceptual gaps (rules from the source that were never implemented) and implementation bugs (rules that were attempted but coded incorrectly).

The operator is a retail trader in Mumbai, India (IST, UTC+5:30) trading a simulated $50,000 futures evaluation account. Correct timezone handling is not cosmetic — it is the difference between trading a kill zone and trading the lunch dead zone.

---

## 2. SOURCE OF TRUTH #1 — THE ICT 2022 MENTORSHIP RULEBOOK

The notes below are the complete rule set, transcribed from ICT's 2022 Mentorship (Episodes 2–41), originally compiled by Tanja (@TanjaTrades). **This is the specification.** Every item here is a candidate requirement. Where the code silently omits one, that is a finding.

YouTube links are provided so you can verify an episode's content directly if a rule is ambiguous.

### Ep 2 — Liquidity, Stop Hunts, FVG Basics
https://www.youtube.com/watch?v=tmeCWULSTHc
- Short-term lows hold sell stops; short-term highs hold buy stops. Algorithms draw price to stops.
- Expect a stop hunt on buy stops before any significant move **lower**, and on sell stops before any significant move **higher**.
- In consolidation, mark S/R on the 1h, wait for the stop hunt, then drop to the lower timeframe and look for imbalances.
- **"The 1, 2, 3 min charts are much better than 5 min because they offer the best view for finding imbalances in indices. Algos work on small time frames."**
- BOS = break of structure. Entry in the FVG. Exit where liquidity lies (most recent old low / old imbalance). Stop = top of the next candle above the FVG.
- Use fib levels and the **50% mark** to determine premium (above 50% = expensive) vs discount (below 50%).
- **Sweet spot: 8:30–11:00 EST.**
- Bearish recipe: buy stops run → break in market structure → enter short in the FVG → target the most recent low before it. Inverse for bullish.

### Ep 3 — Internal Range Liquidity, Order Blocks
https://youtu.be/nQfHZ2DEJ8c
- Internal Range Liquidity = short-term highs/lows **inside** the leg being retraced.
- **FVG definition:** candles before and after the reversal candle. When the candle's high before the reversal does not meet the low of the candle after, it creates a gap. **Only use FVGs at major levels — when a swing low/swing high was taken out.** (Explicitly: not random FVGs.)
- If there are two FVGs, price may dip into the lower one first, retrace back to the higher one — **enter the higher one**.
- **Order block = a change in the state of delivery.** A series of candles into buyside or sellside liquidity.
- **Entry limit = opening price of the order block + 3 ticks for spread.**
- Not every down-close candle is a bullish order block; not every up-close candle is a bearish order block.

### Ep 4 — The 8:30 Hunt
https://youtu.be/L-ReMHiavPM
- **8:30am ET "starts the hunt"** — look for old highs/lows to be overtaken, then a break of market structure.
- Journal timings: structure shift → FVG, entry → target, and drawdown weathered.
- **Start on the 15m or 5m to see the stop hunt, then switch to 2m for the reversal/FVG setup.**

### Ep 5 — The No-Trade Hour
https://www.youtube.com/watch?v=N29ZJ-o31xs
- **Noon to 1pm ET = no trade period.** Not clean price action.
- What warrants a stop hunt: draw horizontal lines at the most significant swing high/low **prior to 8:30am**, then switch to the 5m.
- 3-drives pattern pressing into liquidity.
- **Displacement** = the energetic, pronounced move in the opposite direction.
- **The day is designed with a morning move, a lunch hour you don't trade, and an afternoon move.**
- **A macro algorithm starts running at 1:30pm ET in equities.** If bullish after 1:30pm: find the first swing low, wait for the stop hunt, go long after it.
- News creates noise — sit out.
- Don't micro-scalp.
- **After a good morning trade, switch to demo in the afternoon.**

### Ep 6 — FVG Construction (Authoritative)
https://www.youtube.com/watch?v=Bkt8B3kLATQ
- **Bearish FVG (3 candles):** candle 1 runs over an old high; candle 2 extends low; candle 3 continues. **Candle 3's high must not trade back to candle 1's low — it must create a gap.**
- **Do not look for random FVGs — it must run above a single high or multiple highs (e.g. a double top).**
- **Stop goes above candle 1 or candle 2.** "That stop may feel like a lot of range — you want a lot of range when you're starting out."
- **Bearish MSS: rally above old highs, then quickly shift lower with significant displacement.**
- **Bullish FVG:** market runs below an old low (or multiple lows) for sellside liquidity, then quickly shifts higher and takes out a short-term high.
- Always mark 8:30 EST and look left to the first swing high.
- **Take profit at previous FVGs and at sell stops / buy stops.**
- **Better to take part of the position off and keep the same stop** — trailing gets you stopped out early.
- **Close partials at internal range liquidity (previous FVG or 50% fib), close the remainder at external range liquidity (below intraday lows).**

### Ep 7 — Daily Bias
https://www.youtube.com/watch?v=G8-z91acgG4
- **Risk less than 1% when starting, especially without a clear bias.**
- **Bias = reading the daily chart and deciding where the next day goes. Write your bias down each morning.**
- Consolidation on the daily makes bias hard → drop to smaller timeframes, look for liquidity pools, be nimble, take money and run.
- **Uses /ES to gauge /NQ entries — they move in tandem.**
- **Watches E-mini Dow for divergence to CONFIRM an already-established bias.** By itself divergence means nothing — "he blew accounts just looking for divergences." You need a narrative.
- **Macro** = something inside the algorithm that prevents delivery of price.
- Algorithms run on **time and price**.
- 9:30 open is typically sloppy/volatile.

### Ep 8 — Kill Zone Restatement
https://www.youtube.com/watch?v=7rbV8aWkcqY
- **Hunt for setups 7–10am ET (New York session) or 2–5am ET (London session). These are the two windows.**

### Ep 9 — Power of 3
https://youtu.be/iZLXnNiZm_s
- **Power of 3 = Accumulation, Manipulation, Distribution.**
- Bullish day: open near the low, make a lower low, rally, create the high, close near the high.
- **Anticipate a "false move" / fake run — get your entry during those stop runs.**
- Confirmations needed: did it take out a short-term low, is it inside an FVG, did you get an order block earlier?
- **Bullish order block = consecutive down-closed candles right before a price surge that has an imbalance (displacement).**
- Large overnight run (2–5am): avoid the opening range low, expect premarket discount. Don't chase.
- **Don't place the stop at the direct bottom of the FVG — put it at the bottom of the candle before it.** (Allow for imperfect delivery.)
- After a large run, expect consolidation; wait for a swing low.

### Ep 10 — Economic Calendar
https://www.youtube.com/watch?v=S9ORTYmXwdE
- Calendar at forexfactory.com. Yellow = low impact, orange = medium, red = high.
- **Opening range** = from the open to the high; that range is where FVGs and stop raids happen. Gives leeway for entries near the opening price. **If price leaves that area, don't chase.**
- **Many times the low of day on a large down day forms near 3:30pm — that is distribution.**
- **Likes the 15m timeframe for day trading setups — "it gives you the full picture of what price wants to do."**
- Energetic candles = market structure shift.
- **Start on higher timeframes and work down until you find the FVG. "If you don't have it on the 1 min chart then you don't have a trade."**
- **If bias is bearish, do NOT take a bullish FVG entry. Write your bias down each morning.**

### Ep 11 — Opening Price Anchors
https://www.youtube.com/watch?v=Sqw2bww93Zo
- **Entire daily range → use the midnight opening price. Morning session → use the 8:30am opening price.**
- Intermediate high = lower high. Lower highs confirm bearish structure.
- **After a big move, don't trade the morning session.**
- Don't rush back in after a big win. "If you keep pushing your edge you are going to dull it."

### Ep 12 — Advanced Market Structure
https://youtu.be/8GkQfdAXZP0
- **All minor lower-timeframe swings are subordinate to daily candle structure.**
- **ITH (Intermediate-Term High):** has a lower short-term high to the left **and** to the right of it, or it trades back up to fully rebalance an imbalance.
- **ITL (Intermediate-Term Low):** higher low to the left and to the right = bullish structure.
- **In a bullish move, down-closed candles should not be violated — they act as support.** In a bearish move, up-closed candles should not be breached — they act as resistance.
- **If your ITH is broken to the upside and you're bearish, your idea was wrong — move to the sidelines. Do not force it.**
- Keep perspective to a **5-day horizon**.
- **Fib drawn from LTL to ITH** (not LTH) — because the ITH is where the retracement begins.
- **Bearish order block = consecutive up-closed candles before the move lower. Not just the last one.**
- Zoom to smaller timeframes: **is the down-closed candle followed by an imbalance? If yes, that is a high-probability bullish order block.**

### Ep 13 — Order Blocks In Action
https://youtu.be/tpPtItWqmlg
- Bullish: down-closed candles act as support; **if consequent candles wick into their bodies, that is a possible entry. Take the OPENING price of that candle and extend it out in time.**
- Bearish: up-closed candles act as resistance and should not be broken through.
- **The 9:30 open is often a "Judas swing" — a fake out.**
- **Entry = discount market entry (below 50%), hunt for an FVG within that order block bounce on the smaller timeframe.**
- **Exit = where the liquidity is — prior buy stops.**
- **Once an FVG fills, an ITL low is created and should not be taken out.**
- **Trailing stop must go below the previous down-closed candle / bullish order block's low**, else you get stopped out early.
- **Pyramids: 3 micros at initial entry, then 2 more, then 1 more.**

### Ep 14 / Ep 15 — Live Examples
https://youtu.be/NUdu1n-ML98 · https://youtu.be/tGxuitjtO88
- **Bottom of the FVG can be taken out by morning volatility — wait for price to re-enter the FVG.**
- FOMC day: trade the morning, but be done early.

### Ep 16 — Multiple Setups
https://youtu.be/EpGQnhjXBq8
- **Daily swing high takes out a previous high, then the next day's high is lower → the day after, look to go short.**
- **Index futures: two opening prices matter — midnight, and the 8:30am EST candle.**
- **Bearish: ideally you want to see the market running ABOVE the opening price as manipulation.**
- **Always extend the OPENING of the order block candles as your level.**
- **Fib retracements drawn on candle BODIES, not wicks. ("Wicks and tails are distractions.")**
- **Best setups combine multiple ideas: daily likely lower + bullish daily order block + multiple equal lows = liquidity + fib level.**
- **Max 2 trades in the morning and 2 in the afternoon.** Right at the open is the most volatile — let the initial move qualify what you expect.
- **15m gives the framework.**
- **No entries 12–1pm ET, but you can take profit if already in a trade.**
- **If you miss one FVG, look for the next one if your price target hasn't been hit.**
- **If you have 2 FVGs, anticipate price going into the deeper one, but use the SHALLOWER one as your entry.**

### Ep 17 — Forex / Session Anchors
https://youtu.be/5WIqHJDQ_p4
- **Bearish + 8:30 open lower than the midnight open → use the LOWER one** (sets the minimum threshold for a Judas swing).
- **Bullish → look for a Judas swing below the 8:30 open and go long after.**
- **Pad your exit limit by a few ticks before the exact level** — be forgiving, incorporate spread.
- **Indices: focuses on 8:30–11am ET. Fine entering at 11:45am.**

### Ep 18 — Bias Discipline
https://youtu.be/eai0nHhAC8w
- **Always start bias analysis on the DAILY chart.**
- **Stick to your bias; only take setups in that direction unless you are proven absolutely wrong.**
- Screen in 3 parts: daily, hourly, 15m. **Always referring to the 15m.**
- **After a swing high / buyside liquidity is hit: is there displacement down? Does it create an imbalance? Is there an FVG? → bearish setup.**
- **When there's a large imbalance, put the stop at the TOP of that imbalance, not at the candle before it.**
- **What makes an order block valid? It has to have an imbalance AFTER it.**
- **Can hold through lunch, but if not entered by 11am, wait for the afternoon.**
- **Does not recommend trading gold futures short-term — event-driven, heavily manipulated, lots of stop hunts.**

### Ep 19 — Order Block Mechanics
https://youtu.be/IEa1N0rTtbc
- You don't need perfect entries — you need sound money management.
- **For bearish order blocks use the low and the opening price of the LOWEST up-closed candle.**
- **Order blocks are "bookmarks" for algorithms — they come back to that spot later to fill imbalances, which provides entries.**
- **Mean threshold = the 50% price level of an order block.** The easiest draw is into the low of the candle; the 50% threshold is the next level. **Pick the lowest hanging fruit.**
- **If price has gone down to equilibrium or short-term discount, it is likely to go higher the next day.**
- **Mark the midnight open and the 8:30 ET open. Judas swing + FVG + order block = great entry.**
- **Don't paper trade with leverage — it becomes a video game. Make it boring. Focus on points, not money.**

### Ep 20 — Relative Equal Highs
https://youtu.be/Q6GFu8-Z4rY
- **The market does not like to leave relative equal highs. Retail sees them as resistance; the market runs through them later.**

### Ep 21 — Intermarket Confirmation
https://youtu.be/kmVXVJE08eQ
- **Midnight frames the London 2–5am session.** Doesn't trade it, but checks whether the daily bias is working (did a Judas swing happen followed by displacement in the direction of the bias).
- **Never rallied above the midnight open, and never above the 8:30 open, and we're bearish = extremely bearish.** The market won't rally for you; you either find small pockets of imbalance or miss the move.
- **Trades typically last 90 minutes to 2 hours max.**
- Does not hold overnight.

### Ep 22 — Premium / Discount Restated
https://youtu.be/QKc_i90chVg
- **Trading above an old high = short-term premium (going into liquidity). Trading into an old low = discount.** (Things can be at a premium and go higher — that's why you need the narrative.)
- **If bearish and NQ makes a bigger buy-stop run than ES while ES is weak, that confirms the move lower.**

### Ep 23 — Sweep vs Run
https://youtu.be/QKc_i90chVg
- **Sweep = shallow run through liquidity that reverses. Run = goes through liquidity and continues.** These are different and must be distinguished.

### Ep 24 — Setup Validity
*(no link)*
- **Must incorporate the element of TIME.**
- **Do not impulsively enter without a setup.**
- **Where setups form (bearish): sweeps above old highs and displaces lower, creating an FVG to short into. Or goes into a previous bearish FVG and displaces lower, creating an FVG to short into.**
- **"If this structure doesn't happen, you don't enter the trade. And you have to be okay missing big moves."**

### Ep 25–28 — Psychology, ES Examples
*(no links; Ep 28 is a short execution clip)*
- Don't try to pick exact bottoms.
- **Counter-trend: waiting to go long in the afternoon after consolidation — wait until you're at a DISCOUNT, and in a previous FVG or a break of structure with an FVG after.**
- **Bullish: find the lunch consolidation lows and wait for the break of them to go long.**

### Ep 29 — SMT Divergence
https://youtu.be/8z6My18WZqA *(Ep 33 link; Ep 29 has no direct link in the notes)*
- **Long bias because relative equal highs were left untapped — that is the draw on liquidity.**
- **NQ made a lower low while ES resisted going lower. The same divergence repeated at 11am.**
- **Best to enter in an FVG within a 50% or higher retracement within the displacement.**
- **Close-proximity entry: if you miss your entry, you can get in near it, or at the next BOS + FVG, as long as the R:R is good.**
- **Chose the long in ES because it showed relative strength via the divergence and matched the long bias.**

### Ep 30 — Relative Equal Highs
- **Always look at relative equal highs and expect them to be run.**

### Ep 33 — Mean Threshold Breakout
https://youtu.be/8z6My18WZqA
- **When the mean threshold (50%) of a bearish order block is taken out on the daily, it bodes well for taking out the next short-term high (the top of the bearish imbalance).**

### Ep 37 — News Days
https://youtu.be/HuZurY0ghDI
- **Does not advise trading Non-Farm Payroll days. Don't trade them.**
- **If you made money in the first days of the week, take those days off.**
- **Backtesting and annotating creates positive self-talk — never write anything negative in your journal.** You must annotate and journal to succeed.

### Ep 38 — FVG Lifecycle
https://youtu.be/36184dDAqtM
- **He does not believe imbalances need to be filled fully.**
- **Narrative = understanding what price should do, why, and what it will encounter to prove the narrative is underway.**
- **15m pullback into a 15m FVG → switch to 5m. It may not show as a 5m FVG, but shading it from the 15m highlights it.**
- **His YouTube model is mostly for the NY morning session.**
- **ICT teaches: if bullish, buy at or close to the midnight opening price.**
- **When can you trade during lunch? During a sell-stop raid in a retracement during lunch (rather than consolidation) — when the market is trading fast.**
- **"The market should not come back into an FVG a third time — it probably won't hold up that time."**
- **Morning divergence: ES stronger than NQ at the 9:30 open, NQ made the lower low.**

### Ep 39 — Afternoon Rules
https://youtu.be/yFpHbBnsK_c
- **If trying to short, you should be above or near the 8:30am open.**
- **Afternoon session question: what is the daily range trying to do? Expand higher, lower, reverse for a counter-trend move, or consolidate ahead of tomorrow's news?**
- **12–1pm is New York Lunch. If bearish, the market will clear stops during the lunch hour.**
- **A fast market can create a significant high/low during the lunch hour.**
- **Without a narrative you have aimless speculation.**
- **Leans heavily on the TIME element — time of day, week, month, seasonal influences.**
- **Right levels matter: if the framework is still valid but the entry was wrong, use smaller leverage next time.**

### Ep 40 — Partial Profits, News Days
https://youtu.be/koN1ge8bewI
- **Always take partials at the first target, so if it reverses on you, you're paid.**
- **Only trade on days with high-impact or medium-impact calendar events. That is a low-hanging-fruit day.**
- **Moves before the calendar event are a missed opportunity. Let it go.**
- **Trading every day and forcing it makes you more prone to losing trades.**
- **Huge wicks taking out both buyside and sellside (typically FOMC) — ignore those wicks, it's all manipulation.**
- **If directional bias is correct, the London session created the high/low.**

### Ep 41 — FVG Exhaustion + Risk Management
https://youtu.be/2XhDi5GoNUI
- **Prefer to see a stop run in the lunch hour.**
- **Likes to wait until 1:30 for cleaner price action.**
- **"If price action meaningfully bounces from an FVG twice, it should not come back to it and fill it completely a third time."**
- **On moving stops: take partials and keep the initial stop.**
- **Gold standard setup = FVG + Order Block + Optimal Trade Entry after a short-term shift in market structure.**
- **RISK MANAGEMENT: use a calculator to size positions according to risk.**
- **Drawdown must be managed: after a loss, reduce the risk on your next trade by taking a smaller size.**
- **Don't try to make the loss back right away. Longevity + controlled risk + impeccable risk management = consistent profitability.**

---

## 3. SOURCE OF TRUTH #2 — THE TARGET ACCOUNT (MFFU $50,000)

The engine's alerts are formatted for **MyFundedFutures (MFFU)**, a US futures prop firm. These are hard external constraints the code must respect.

### Account rules ($50K, Rapid/Core)
| Rule | Value |
|---|---|
| Profit target | $3,000 (start $50,000 → $53,000) |
| Max loss (EOD trailing) | $2,000 → floor at $48,000 |
| Daily loss limit | None |
| Consistency rule | **50%, evaluation only** — best single day ≤ 50% of total profit → **$1,500 cap on any one day** |
| Minimum trading days | 2 |
| Profit split | 90/10 (Rapid), 80/20 (legacy Core/Flex) |
| Payout buffer | $2,100 above the locked drawdown floor before withdrawals are permitted |
| Minimum payout | $500 |
| Max contracts | 5 minis / 50 micros |
| Permitted instruments | **CME/CBOT/NYMEX/COMEX listed futures only** |
| Prohibited | Equities, options, **cryptocurrency, CFDs, OTC products** |
| Tier 1 news trading | Not allowed on funded stage (allowed in evaluation) |

### Tradovate micro contract specifications (verify these independently — do not trust the file)
| Instrument | Ticker | Contract size | $ per 1.00 move |
|---|---|---|---|
| Micro E-mini Nasdaq-100 | MNQ | $2 × index | **$2.00 / point** |
| Micro Gold | MGC | 10 troy oz | **$10.00 / $1** |
| Micro WTI Crude | MCL | 100 barrels | **$100.00 / $1** |
| Micro Silver | SIL | 1,000 troy oz | **$1,000.00 / $1** |
| Micro Bitcoin | MBT | 0.1 BTC | **$0.10 / $1** |
| Micro Ether | MET | 0.1 ETH | **$0.10 / $1** |

### Consequence the auditor must check
Because MBT/MET pay only $0.10 per $1 of movement, **a $3,000 profit target is not realistically reachable trading crypto futures.** The reachable instruments are MNQ, MGC, MCL. Meanwhile MFFU **prohibits crypto entirely**, so `BTC/USDT` and `ETH/USDT` in `config.yaml` cannot be traded on this account at all — they are only legitimate as SMT-divergence *analysis inputs*. **Verify the engine does not emit tradeable signals for prohibited instruments.**

### Critical operational note
MFFU accounts are **100% simulated** at both the evaluation and "funded" stages. Simulated fills are idealized. Strategies relying on precise limit fills at an FVG midpoint will fill perfectly in simulation and may not fill live. Any backtest or forward-test result from this environment should be treated as optimistic.

---

## 4. THE ARTEFACT UNDER AUDIT — MAP AND CLAIMS

| File | LOC | What it claims to do |
|---|---|---|
| `main.py` | 403 | Scanner loop, cloud HTTP server, dashboard HTML, signal state, alert dispatch |
| `src/core/models.py` | 129 | Dataclasses: `Candle`, `SwingPoint`, `FairValueGap`, `OrderBlock`, `BreakerBlock`, `SMTResult`, `ICTSignal` |
| `src/core/sessions.py` | 107 | Kill zone detection in America/New_York, dual NY/IST labels, midnight-open lookup |
| `src/core/market_structure.py` | 133 | Swing points, liquidity sweeps, MSS, displacement validation |
| `src/core/pd_arrays.py` | 128 | FVGs + consequent encroachment, order blocks + mean threshold, premium/discount |
| `src/core/smt.py` | 87 | SMT divergence between a correlated pair |
| `src/core/risk_manager.py` | 84 | OTE fib levels, position sizing, drawdown-mitigation rule |
| `src/core/mffu.py` | 118 | Contract specs, ticker mapping, trade metrics |
| `src/engine/detector.py` | 337 | **Master pipeline** — the heart of the system |
| `src/engine/fetcher.py` | 189 | OKX/ccxt crypto + Yahoo Finance futures/commodities data |
| `src/config/settings.py` | 57 | YAML config loading |
| `src/alerts/*.py` | 202 | Console / Telegram / Discord formatting |
| `tests/test_ict_engine.py` | 80 | Unit tests |

### Design decisions already made (do not re-litigate — audit against them)
1. **Risk per trade = 0.5% of $50,000 = $250.** (Deliberately reduced from 1.0% because the $2,000 EOD drawdown only survives 4 losing trades at 1%.)
2. **Traded instruments are MNQ and MGC.** BTC/ETH are analysis-only (SMT), because MFFU forbids crypto.
3. **Minimum R:R gate = 2.5.**
4. **Dashboard must always render**, including when no signal is active.
5. Timezone of record is `America/New_York`; IST is a display convenience for the operator.

### Pre-verified facts (confirmed by grep before this prompt was written)

I have already confirmed the following with `grep`. **Do not spend time re-verifying the grep result itself — verify the implication and the blast radius instead.** If any of these turn out to have a mitigation I missed, say so explicitly.

```
ICTRiskManager is imported and used only as a static method:
  detector.py:30   from src.core.risk_manager import ICTRiskManager
  detector.py:175  ote_levels = ICTRiskManager.calculate_ote_levels(...)
  detector.py:275  ote_levels = ICTRiskManager.calculate_ote_levels(...)
  → the class is never instantiated outside tests/test_ict_engine.py:37
  → H29 CONFIRMED at the grep level

fixed_risk_percent is loaded but never consumed:
  settings.py:18   fixed_risk_percent: float = 1.0     (stale default — config.yaml says 0.5)
  settings.py:43-44  cfg.fixed_risk_percent = float(...)
  risk_manager.py:74  calculate_position_size(...)
  → no caller passes it and calculate_position_size is never invoked
  → H30 CONFIRMED at the grep level

target_3 always resolves to the -1.00 extension:
  detector.py:179  target_3 = max(ote_levels["ext_062"], ote_levels["ext_100"])
  detector.py:279  target_3 = min(ote_levels["ext_062"], ote_levels["ext_100"])
  → ext_100 is by construction the larger (bullish) / smaller (bearish) value
  → ext_062 is unreachable; H17 CONFIRMED at the grep level

Order block index lookup uses value equality:
  pd_arrays.py:105  idx = candles.index(ob_candle)
  pd_arrays.py:120  idx = candles.index(ob_candle)
  → Candle is a mutable dataclass, so .index() matches on OHLCV equality
  → H10 CONFIRMED at the grep level

Server binding is correct:
  main.py:229  server = HTTPServer(("0.0.0.0", port), CloudHealthServer)
  main.py:378  port = int(os.getenv("PORT", "8080"))
  → H42 REFUTED (no action needed)
```

Additionally: `src/config/settings.py:18` hardcodes a default of `fixed_risk_percent = 1.0`, which now contradicts `config.yaml` (0.5). Since the value is never consumed this is currently harmless, but any future wiring will silently pick up 1.0 if the YAML key is missing. Add this as **H46**.

---

## 5. THE VERIFICATION PROTOCOL

Work through these phases in order. Do not skip ahead to writing the report.

### Phase 1 — Inventory (no judgement yet)
Read every file. Produce a one-paragraph description of what each module *actually* does (not what its docstring says). Note any function that is defined but never called, and any config key that is loaded but never used.

### Phase 2 — Rule Coverage Matrix
Build a table with one row per rule from §2. Columns:
`Rule | Episode | Implemented? (Yes / Partial / No) | File:Line | Auditor's note`

Be ruthless. "Partial" must be justified. A rule is **No** if there is no code path that enforces it. Pay particular attention to these, which I believe are absent but you must confirm:
- Daily-chart bias determination (Ep 7, 10, 16, 18, 19)
- Economic calendar / news-day filter, including the NFP avoidance (Ep 10, 37, 40)
- The "only trade days with medium/high-impact events" filter (Ep 40)
- Power of 3 / Judas swing logic (Ep 9, 10, 16, 17, 21, 38)
- Sweep vs Run distinction (Ep 23)
- Partial profit taking schedule (Ep 6, 40, 41)
- Max 2 trades per session (Ep 16)
- External range liquidity as the final target (Ep 6)
- Pyramid/add-on sizing (Ep 13)
- Trade duration management (Ep 21: 90 min–2 h)
- Relative equal highs/lows detection (Ep 20, 29, 30)
- Higher-timeframe FVG shading down to the execution timeframe (Ep 38)

### Phase 3 — Module Correctness Review
For each core module, state whether the implementation is faithful to §2, then test the specific hypotheses below. **Each hypothesis is a claim by me, not a fact. Confirm or refute with file:line evidence.**

**`sessions.py`**
- H1: The hardcoded IST strings in every session label assume **EDT (UTC−4)**. `zoneinfo` handles DST correctly for the NY-side *logic*, but the printed IST times will be **one hour wrong for roughly five months of the year** (when New York is on EST, UTC−5). Confirm, and give the exact date ranges.
- H2: `is_killzone_active()` returns True for "Asian Range", which ICT frames as a *range to be mapped*, not a window to execute in. Assess whether this constitutes a false positive.
- H3: There are time gaps (e.g. 13:00–13:30, 00:00–02:00, 05:00–07:00) that fall through to "Out-of-Killzone". Confirm this is intentional and matches Ep 5 / Ep 41 ("wait until 1:30").
- H4: `get_ny_midnight_open()` scans backwards for the first candle at exactly 00:00 and returns `c.open`. On a 5m series with gaps (weekends, halts, missing bars) this can return a stale or wrong price. Assess.

**`market_structure.py`**
- H5: `find_swing_points(left_bars=2, right_bars=2)` requires 2 bars on the right, so the 2 most recent bars can never be swing points. Assess the latency this introduces on a 5m chart.
- H6: `detect_market_structure_shift()` takes `bullish_swings[-1]` / `bearish_swings[-1]` — the last swing **by list order**, which is index order. Confirm that is genuinely the most recent relevant swing and not e.g. the highest/lowest.
- H7: The function evaluates both bullish and bearish branches inside the same ascending loop and returns on the first match. If a low is swept and the first displacement candle closes below a prior swing low, it returns BEARISH for a bullish setup, which the caller then discards with `continue` — **potentially discarding a valid bullish setup that would have been found a few bars later.** Assess.
- H8: `check_displacement()` uses a hardcoded `multiplier=1.4` on average body height and a 0.55 body/range ratio (the docstring says 60%, the code says 0.55 — confirm). Is 1.4× a defensible encoding of "energetic / pronounced move"? It is never calibrated to volatility or instrument.
- H9: `SwingPoint.swept` is declared but never set anywhere. Confirm it is dead.

**`pd_arrays.py`**
- H10: **BUG — `find_order_block()` computes `idx = candles.index(ob_candle)`.** `Candle` is a plain dataclass, so `.index()` uses value equality and will return the **first candle anywhere in the series with identical OHLCV**, not the order block's true position. On a 5m series this can be off by hundreds of bars. Confirm and propose a fix (carry the index from an `enumerate`).
- H11: **DEVIATION — for a bullish order block the code selects `min(down_candles, key=lambda c: c.low)` (the LOWEST low) among the 5 candles before displacement.** Ep 12/19 say the bullish order block is the **last** down-close candle before the surge (and "consecutive down-closed candles"). Lowest ≠ last. Assess the impact.
- H12: The order block is searched only in the 5 candles before `mss_idx`. Justify or challenge this window against Ep 12 ("consecutive up/down closed candles", not a single candle).
- H13: `mean_threshold` is computed on the candle **body** (body_bottom + 50% of body height). Ep 19 defines the mean threshold as "the 50% price level of an order block". Determine whether body or full range (high/low) is correct, and note that `OrderBlock` stores `high`/`low` but the MT uses neither.
- H14: `find_fair_value_gaps()` filters with `min_gap_percent=0.05`. On MNQ at ~20,000 that is ~10 index points; on MGC at ~2,600 it is ~$1.30. Assess whether a single fixed percentage is appropriate across instruments with wildly different tick sizes and volatility.
- H15: FVG `top`/`bottom` semantics: bullish sets `top=c3.low, bottom=c1.high`; bearish sets `top=c1.low, bottom=c3.high`. Verify both against the Ep 6 definition and verify every downstream consumer assumes the same convention.

**`detector.py`**
- H16: **BUG — bounce counting in `audit_fvg_lifecycle()` increments `bounces` for every candle whose range overlaps the FVG.** Several consecutive candles sitting inside the gap during a single retracement each increment the counter, so one retest can register as 3+ "bounces" and be wrongly invalidated. Ep 41's rule is about **two distinct bounces**, not two candles. Confirm and propose a fix (count touches separated by a candle that leaves the zone).
- H17: **DEVIATION — `target_3 = max(ote_levels["ext_062"], ote_levels["ext_100"])` always resolves to `ext_100`**, since the −1.00 extension is by construction larger than −0.62. So `ext_062` is dead, and R:R is computed against the most optimistic possible target. Confirm, then assess: does the `min_risk_reward=2.5` gate become meaningless because it is measured against the −1.00 full-delivery extension rather than target 1 or target 2? Recommend what R:R should be measured against.
- H18: `target_1 = displacement_high` (the extreme of the displacement leg). Ep 6 says to target internal range liquidity — previous FVGs and resting stops. Assess whether the displacement high is a defensible first target.
- H19: **Order Block Mean Threshold invalidation (`if any(c.close < ob.mean_threshold ...)`) scans every candle since the FVG formed.** A normal deep retracement into the FVG will often close below the OB mean threshold, invalidating setups that Ep 12/13/33 would treat differently. Determine the intended reading of the mean-threshold rule and whether this implementation over-fires.
- H20: The runaway-expansion check (`hit_target_first`) **permanently** rejects the setup via `continue` for as long as the sweep remains in the 25-bar scan window. Confirm it does not permanently suppress a symbol.
- H21: `recent_swings = [s for s in swings if s.index >= len(ltf_candles) - 25]` — a 25-bar lookback on 5m = ~2 hours. Assess whether this is consistent with the kill-zone framing, and what happens to a sweep that occurred earlier in the session.
- H22: `detect_liquidity_sweep(..., lookforward_window=10)` — a swept level is only recognised if price returns within 10 bars. Assess coverage.
- H23: `buffer = max(sweep_low * 0.0005, 0.05)` — 0.05% of price. On MNQ at 20,000 that is 10 index points ($20 on 2 contracts). Ep 6 says the stop should be **above candle 1 or candle 2 of the FVG**, and Ep 18 says **above the top of a large imbalance** — not a fixed percentage below the sweep extreme. Assess whether this is a faithful encoding and whether 0.05% is adequate for each instrument in the universe.
- H24: If `find_order_block()` returns `None`, all order-block validation is **skipped silently** (`if ob:`). Assess whether a missing OB should invalidate the setup rather than pass it.
- H25: The premium/discount filter compares `sweep_low > htf_eq` using an HTF range built from **30 one-hour candles (~30 hours)**. Ep 2/22 frame the dealing range against the session or the daily. Is 30 hourly bars the correct dealing range?
- H26: `ny_midnight_open` is used **only** to append a confluence string. Ep 16/17/19/21/38 use it as a directional filter (bearish wants price above the open; bullish wants price below). Assess whether it should be a filter rather than a decoration.
- H27: There is no check that the FVG occurs **after** a run on an old high/low in the correct direction beyond the sweep→MSS window, and no check for "relative equal highs/lows" (Ep 20, 30).
- H28: Determine the effective lookback: with `ltf_candles` limited to ~100 bars of 5m data, is there enough history for swings → sweep → MSS → FVG to chain without truncation?

**`risk_manager.py`**
- H29: **DEAD CODE — `ICTRiskManager` is never instantiated in `detector.py` or `main.py`.** Only the static `calculate_ote_levels()` is used. The drawdown-mitigation rule (halve risk after 2 consecutive losses; restore after 2 consecutive wins) is therefore **never applied in production**. Confirm, and state the impact on the Ep 41 drawdown-management requirement.
- H30: `fixed_risk_percent` (0.5) is loaded from `config.yaml` but appears to be **unused for actual position sizing** — no signal carries a quantity, and `mffu.py` hardcodes `default_qty: 2`. Confirm, and state what is required to make risk-based sizing real.
- H31: `calculate_ote_levels()` returns `ext_027` computed with `0.272` (a typo-level difference from 0.27, but confirm intent), and returns retracement levels (`retrace_618/705/790`) that **no caller uses**. Note the gap: ICT's Optimal Trade Entry is a *specific* retracement zone (61.8–79%), and the engine emits none of it in the signal.

**`smt.py`**
- H32: Compares the last two swing lows (or highs) of each asset with **no timestamp alignment** — asset A's two lows and asset B's two lows may come from different times. Ep 22/29/38 describe divergence observed **at the same moment** (NQ lower low while ES refuses). Assess.
- H33: No correlation or cointegration precondition, and no check that the two series have comparable bar counts or that both are in the same session.
- H34: `lookback=25` on 5m ≈ 2 hours. Assess appropriateness.
- H35: Verify the SMT benchmark routing in `fetcher.get_smt_benchmark_pair()` covers the configured universe correctly (NQ↔ES, GOLD↔SILVER, BTC↔ETH) and that the global `smt_benchmark` fallback in `config.yaml` cannot produce a nonsense pairing (e.g. NQ vs ETH).

**`fetcher.py`**
- H36: Futures/commodities come from **Yahoo Finance (`query1.finance.yahoo.com`)** using `NQ=F`, `ES=F`, `GC=F`, `SI=F`, `CL=F`. These are front-month continuous quotes with no crumb/session cookie, may be delayed, are rate-limited, and are frequently unavailable from datacenter IPs. **Assess the reliability of this as a production data source for a 60-second scan loop**, and note that the audited instruments (NQ=F) are **not** the traded instruments (MNQ).
- H37: `fetch_commodity_candles()` silently maps any timeframe that is not 1m/5m → 5m; 15m/1h → 1h; everything else → 1d. So a requested 15m silently becomes 1h. Confirm and assess.
- H38: Both fetch paths attach `tz=timezone.utc` to timestamps — verify this is correct for Yahoo (epoch seconds) and ccxt/OKX (epoch milliseconds), and that no path can produce naive datetimes which `sessions.to_ny_time()` would then mis-convert.
- H39: `fetch_candles()` swallows all exceptions in the exchange loop with `except Exception: continue` and then falls through to a direct OKX call that will raise on failure — meaning a total data outage may surface as an unhandled crash or an empty list rather than a clean error. Assess error handling end to end.
- H40: The universe in `config.yaml` still contains `BTC/USDT`, `ETH/USDT`, `SOL/USDT` and `NQZ2026`. Confirm whether the engine would emit tradeable (as opposed to analysis-only) signals for instruments MFFU prohibits.

**`main.py` / alerts / deployment**
- H41: Confirm the dashboard renders correctly with **no active signal** and with **zero fetched candles** (see §3 note about Binance returning HTTP 451 from datacenters, which is why OKX/Gate.io/Kraken are used — verify that fallback still holds).
- H42: Verify the HTTP server binds `0.0.0.0` and reads the port from the environment (`PORT`), as required by Render/Railway.
- H43: Check for any blocking network call inside the request handler, and for whether the scan loop and the HTTP server can starve each other.
- H44: Confirm no secrets are hardcoded and that Telegram/Discord credentials come from environment variables.
- H45: `tests/test_ict_engine.py` is 80 lines for a 2,050-line codebase. State plainly what coverage exists and what critical paths (kill zone logic, FVG lifecycle, order block indexing, premium/discount) are untested.

### Phase 4 — Cross-cutting logic audit
- Trace a single signal end to end and report every place a `None`, an empty list, a negative risk, or a division by zero could propagate.
- Identify any place where a signal could be emitted with `stop_loss` on the wrong side of `entry_price`, or with `risk_reward_ratio` computed from a zero/negative risk.
- Identify any O(n²) or worse loops given `limit=100` candles and a 60-second scan interval across 7 symbols.
- Confirm the `Candle` dataclass being mutable and unhashable does not cause aliasing bugs where candle lists are sliced and passed around.

### Phase 5 — Methodology fidelity verdict
Answer these directly:
1. Is this a faithful implementation of the ICT 2022 Mentorship model, or an approximation that borrows its vocabulary? Be specific and blunt.
2. Which **three** omissions most damage signal quality?
3. Which **three** bugs most damage correctness?
4. If this engine ran unattended against a live $50K evaluation account tomorrow, what is the single most likely way it fails?

---

## 6. OUTPUT FORMAT

Produce a report with exactly these sections. No preamble, no pleasantries, no restating my prompt back to me.

### Section A — Executive verdict
Three to five sentences. Overall fidelity assessment (as a percentage, with justification), and the blunt answer to "would you run this against a funded account?".

### Section B — Severity-ranked findings table
`ID | Severity (CRITICAL / HIGH / MEDIUM / LOW) | Category (Bug / Omission / Deviation / Data / Risk / Test) | File:Line | Finding | Source rule violated | Recommended fix`

Severity definitions:
- **CRITICAL** — produces incorrect signals or crashes; must be fixed before any live use
- **HIGH** — materially degrades signal quality or violates an explicit rule
- **MEDIUM** — deviation from the source material with moderate impact
- **LOW** — cosmetic, stylistic, or defensive

### Section C — Rule coverage matrix
The full table from Phase 2. Every rule from §2 gets a row.

### Section D — Hypothesis resolution
For H1–H45: `ID | CONFIRMED / REFUTED / PARTIALLY | Evidence (file:line) | Notes`
Where refuted, say so plainly — I would rather be wrong than misled.

### Section E — Minimal patch set
For each CRITICAL and HIGH finding, give the exact code change. Prefer small, surgical diffs over rewrites. Do not redesign the system; I want it correct, not different. If a fix requires a design decision, present the options and recommend one.

### Section F — Implementation backlog
Ordered, with an estimated effort (S / M / L) for each remaining MEDIUM and LOW item, plus the Phase 5 omissions that need building from scratch.

### Section G — Confidence and limitations
State explicitly what you could **not** verify without live market data, and what assumptions you made. If any of my §4 "design decisions already made" are themselves wrong, say so here — I would rather hear it than have you work around it.

---

## 7. GROUND RULES FOR YOUR ANALYSIS

1. **Cite file and line for every claim.** No unsupported assertions.
2. **Distinguish four categories.** A *bug* is code that doesn't do what it intends. An *omission* is a source rule with no implementation. A *deviation* is an implementation that contradicts the source. A *data* issue concerns provenance, latency, or availability. Do not conflate them.
3. **Do not fix things I did not ask about.** No stylistic rewrites, no type-hint campaigns, no framework migrations.
4. **Do not flatter the code.** It was written fast. Empty praise wastes my time.
5. **Quantify where possible.** Instead of "the buffer may be too small", give the dollar impact on 2 MNQ at 20,000.
6. **If you disagree with a rule in §2 on trading grounds,** flag it — but implement and audit against what the source says, not what you think is better.
7. **Never assume a function is called.** Grep for every symbol you discuss.
8. **Financial disclaimer required in Section A:** one sentence noting this is an audit of code against a specification, not investment advice, and that all MFFU accounts are simulated.
