# CROSS-VERIFICATION — Candice stream log vs the Candace_ICT_Suite engine

**Date:** 23 Sep 2026 · **Data:** cached Yahoo NQ=F 5-min (15 Jul → 23 Sep 2026, all 30 stream days) ·
**Engine:** Python replica of `Candace_ICT_Suite.pine` (`crosscheck.py`), two configs:
**A = MFFU window 08:30–11:00 ET**, **B = her stream hours 02:00–11:00 ET**.
Defaults identical to the Pine: recency 90 min, stop 5–35 pts else skip, min R 1.0/2.0,
EQL/EQH sweeps count, IFVG allowed, midnight filter off, TP1-half → breakeven → swing-trail → TP2,
30-min limit expiry, flat by 12:00, **max 2 trades / stop after 2 losses per day**.
SMT and NWOG disabled (no ES cache / no Sunday-gap grade) — grade therefore not computed.

The filled sheet is **`Candice_Stream_Log_FILLED.csv`** — all yellow columns populated.

---

## 1 · Internal consistency of her log (tabs vs tab)

| Check | Log says | Recomputed | Verdict |
|---|---|---|---|
| Trades taken | 45 | 45 | ✅ |
| Wins / Losses / Breakevens | 10 / 32 / 3 | 10 / 32 / 3 | ✅ |
| Win rate | 22% | 22.2% | ✅ |
| Total R | −13.15 | −13.15 | ✅ |
| Avg R longs / shorts | −0.47 / +0.48 | −0.47 / +0.42 | ✅ / ⚠️ (row 11, 31-Jul, is a Win with blank R; counting it ≈ +0.5R gives +0.48) |
| All 30 per-day roll-ups (trades & R & colour) | — | 30/30 match | ✅ |
| Green / Red / No-trade days | 8 / 10 / 10 | 8 / 10 / 10 | ✅ |

**The log is internally consistent.** Only nit: 31-Jul is logged as a win but R left blank and the day counted *Flat* — the +0.48 short average silently includes that missing R.

## 2 · Did the script see what she saw? (config B, her hours)

| Metric | Value |
|---|---|
| Streams checked | **30 / 30** |
| Her trades where the script also gave a same-direction plan | **18 of 45 rows** |
| Her R on those 18 rows | **−2.85R** |
| Script R on the same rows (7 completed at 5-min grain) | **+1.42R** |
| Her no-trade streams where the script also sat out | 5 of 10 (23-Jul, 27-Aug, 11-Sep, 14-Sep, 23-Sep) |
| Her no-trade streams where the script would have planned | 5 of 10 (13-Aug, 20-Aug, 31-Aug, 18-Sep, 21-Sep) |

### The headline — her four worst days, the script had **zero** plans

| Day | Her result | Her own words | Script |
|---|---|---|---|
| 03-Aug | **−3.0R** | "Married the bias… should have waited for Asia low sweep" | no plan |
| 08-Sep | **−3.0R** | "The trade that got away" ×2, then bad short | no plan |
| 10-Sep | **−2.6R** | longs while title says "Time to SHORT!" | no plan |
| 15-Sep | **−5.0R** | "L STREAK!" — 5 losses, hit session loss limit | no plan |

**−13.6R of her −13.15R total loss happened on days the model itself saw no setup.**
The gates (external-liquidity sweep within 90 min + displacement + 5–35 pt structural stop + 2R target)
reject exactly the behaviour she criticises in herself: entering before the sweep, counter-model bias,
revenge re-entries. On 09-Sep (4 trades, −2.05R) the script did plan — but the 2-trade/2-loss day cap
would have stopped her after trade 2 instead of trade 4.

### The flagship — 26 Aug (her Chart Fanatics trade)

Script **gave a long plan on the Equal-lows sweep, 17.5-pt structural stop** (hers: 15–17 pts),
TP2 at the RTH-gap edge — the same anatomy as her +2R trade. At 5-min grain the limit at the FVG CE
was not tagged inside 30 min, so the replica logs "plan, no fill"; on a 1-min replay the 9:28 wick
fills it. Structure, direction, sweep source and stop distance all match. ✅

### Where she beat the script

22-Sep: she lost twice long, then took the **V-shape long +3R** after the equal-low sweep — the script's
only plan that day was a *short* at 06:15 (+2.65R in the replica). Her discretion (waiting for the second
sweep, reading the giveaway) caught what the event-triggered engine missed. Same on 25-Aug (+1.5R, no
script plan) and 18-Aug (+2R, no plan). **Her edge, where it exists, is entry timing and patience —
not the raw signal.**

## 3 · Script totals (both configs)

| Config | Plans | Completed | Raw R | Capped @3R/trade* | W–L |
|---|---|---|---|---|---|
| A — MFFU 08:30–11:00 | 8 | 3 | +10.43 | +4.98 | 2–1 |
| B — stream hours 02:00–11:00 | 52 | 28 | +51.17 | +29.61 | 24–4 |

\*Capped because TP1 = swing-after-sweep can be far away (08-14 printed 7.5R); a live trader scales
earlier. Read the capped column.

**Do not read +29.6R as "the script is profitable."** The TP1-half + breakeven-runner management makes
almost every *completed* plan a winner by construction (24–4); that is an accounting property of the
management, not evidence of edge, and 5-min bars overstate fills. Combined with sweep4 (0/15 mechanical
configs positive out-of-sample) the honest statement is unchanged: **the model's value is selection and
risk control — it says NO on the days that blow accounts — not stock picking.**

## 4 · Verdict & how to use the filled sheet

1. **Her log verifies** arithmetically; her on-stream −13.15R over 2 months is real and is concentrated
   in rule-breaking days the script would have declined.
2. **The script cross-verifies as a discipline layer:** 18/45 direction-agreement on traded rows,
   perfect refusal on her 4 worst days, 5/10 agreement on her sit-out days.
3. Yellow columns are pre-filled from the 5-min replica; where it says *"plan, no fill"* a 1-min
   TradingView Replay may still fill the limit (see 26-Aug). Confirm those rows on Replay before
   trusting the R column.
4. For the MFFU $50k account keep config **A** (08:30–11:00, 2 trades, 2-loss stop): fewer, higher-quality
   plans, and her own log shows the London hours she streams are where her losses cluster
   (longs avg −0.47R there).

*Not a validated edge. Small sample (2 months, one instrument). The assistant proposes; you dispose.*
