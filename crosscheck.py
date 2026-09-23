#!/usr/bin/env python3
"""
CROSS-VERIFICATION ENGINE
Replicates Candace_ICT_Suite.pine (indicator assistant) on cached 5-min NQ=F
data (Yahoo 1-min is rate-limited; 5-min is the same engine at coarser grain).

For every stream date in Candice's log it answers:
  - did the script give a plan? (direction, time, levels)
  - what R would the script's own management have produced?
and matches plans against her logged trades.

Configs:
  A "MFFU"  : entry window 08:30-11:00 ET (the funded-plan window)
  B "STREAM" : entry window 02:00-11:00 ET (her livestream hours)
Everything else identical to the Pine defaults:
  recency 90 min, minSL 5, maxSL 35, minR1 1.0, minR2 2.0, useEQ on,
  IFVG on, midnight filter OFF, SMT off (no ES cache -> grade capped at A),
  2 trades/day, stop after 2 losses, 30-min limit expiry, flat by 12:00,
  TP1 half + breakeven + swing trail (her management).
"""
import csv, json, datetime as dt

TZ = dt.timezone(dt.timedelta(hours=-4))          # Jul-Sep 2026 = EDT
TICK, BUFPX, PADPX = 0.25, 1.0, 1.0
RECB, EXPB = 18, 6                                # 90 / 30 min in 5-min bars

def load():
    bars = []
    for r in csv.reader(open('data/Y_NQ_F_5m_60d.csv')):
        ts = float(r[0]) / 1000
        bars.append((dt.datetime.fromtimestamp(ts, TZ), float(r[1]), float(r[2]),
                     float(r[3]), float(r[4])))
    return bars

BARS = load()
N = len(BARS)

# ---------------- daily OHLC (for PDH/PDL, prior-day candle bias) ----------
daily = {}
for t, o, h, l, c in BARS:
    d = daily.setdefault(t.date(), [])
    d.append((t, o, h, l, c))
DAYH = {d: max(x[2] for x in v) for d, v in daily.items()}
DAYL = {d: min(x[3] for x in v) for d, v in daily.items()}
DATES = sorted(daily)

# ---------------- hourly resample for 1H FVG -------------------------------
hourly = {}
for t, o, h, l, c in BARS:
    hk = t.replace(minute=0, second=0)
    if hk not in hourly:
        hourly[hk] = [h, l]
    else:
        hourly[hk][0] = max(hourly[hk][0], h)
        hourly[hk][1] = min(hourly[hk][1], l)
HKEYS = sorted(hourly)
HIDX = {k: i for i, k in enumerate(HKEYS)}

def h1fvg_at(t):
    """At first 5-min bar of hour H: gap between hourly candles [1] and [3]."""
    if t.minute != 0:
        return None
    i = HIDX.get(t.replace(second=0))
    if i is None or i < 3:
        return None
    h1, l1 = hourly[HKEYS[i - 1]]
    h3, l3 = hourly[HKEYS[i - 3]]
    if l1 > h3:
        return ('bull', l1, h3)
    if h1 < l3:
        return ('bear', l3, h1)
    return None

# ---------------- per-bar context ------------------------------------------
ctx = []
mid = rth_prev = None
aH = aL = lH = lL = None
aHsw = aLsw = lHsw = lLsw = 0
eql_lvl = eqh_lvl = None
eql_sw = eqh_sw = True
last_ph = last_pl = None
ssl = None   # dict(bar, name, lo, loB, hi)
bsl = None
avg_body = []
fvg = []     # dict(t, b, bull, inv)

piv_h = [None] * N
piv_l = [None] * N
for i in range(3, N - 3):
    t, o, h, l, c = BARS[i]
    if h == max(BARS[j][2] for j in range(i - 3, i + 4)):
        piv_h[i] = h
    if l == min(BARS[j][3] for j in range(i - 3, i + 4)):
        piv_l[i] = l

for i in range(N):
    t, o, h, l, c = BARS[i]
    hh, mm = t.hour, t.minute
    prev_t = BARS[i - 1][0] if i else None

    if hh == 0 and mm == 0:
        mid = o
    if hh == 16 and mm == 0 and (prev_t is None or not (prev_t.hour == 16 and prev_t.minute == 0)):
        rth_prev = BARS[i - 1][4] if i else None
    rth50 = None
    if hh == 9 and mm == 30 and rth_prev is not None and abs(o - rth_prev) > TICK:
        rth50 = o + (rth_prev - o) * 0.5

    if hh == 19 and mm == 0 and (prev_t is None or prev_t.hour != 19 or prev_t.minute != 0 or prev_t.date() != t.date() - dt.timedelta(days=0) and False):
        pass
    # asia 19:00-02:00, london 02:00-05:00
    in_asia = (hh >= 19 or hh < 2)
    in_london = (2 <= hh < 5)
    if in_asia:
        if aH is None or (prev_t and not (prev_t.hour >= 19 or prev_t.hour < 2)):
            aH, aL, aHsw, aLsw = h, l, 0, 0
        else:
            aH, aL = max(aH, h), min(aL, l)
    else:
        if aH is not None and aLsw == 0 and l < aL:
            aLsw = i
        if aH is not None and aHsw == 0 and h > aH:
            aHsw = i
    if in_london:
        if lH is None or (prev_t and not (2 <= prev_t.hour < 5)):
            lH, lL, lHsw, lLsw = h, l, 0, 0
        else:
            lH, lL = max(lH, h), min(lL, l)
    else:
        if lH is not None and lLsw == 0 and l < lL:
            lLsw = i
        if lH is not None and lHsw == 0 and h > lH:
            lHsw = i

    # equal highs/lows from confirmed pivots (3-bar lag like Pine)
    if i >= 3:
        ph = piv_h[i - 3]
        pl = piv_l[i - 3]
        if ph is not None:
            if last_ph is not None and abs(ph - last_ph) <= 2.0:
                eqh_lvl = max(ph, last_ph)
                eqh_sw = False
            last_ph = ph
        if pl is not None:
            if last_pl is not None and abs(pl - last_pl) <= 2.0:
                eql_lvl = min(pl, last_pl)
                eql_sw = False
            last_pl = pl

    sEv = bEv = None
    if aL is not None and aLsw == 0 and not in_asia and l < aL:
        aLsw = i; sEv = "Asia low"
    if lL is not None and lLsw == 0 and not in_london and l < lL:
        lLsw = i; sEv = "London low"
    if not eql_sw and eql_lvl is not None and l < eql_lvl:
        eql_sw = True; sEv = "Equal lows"
    if aH is not None and aHsw == 0 and not in_asia and h > aH:
        aHsw = i; bEv = "Asia high"
    if lH is not None and lHsw == 0 and not in_london and h > lH:
        lHsw = i; bEv = "London high"
    if not eqh_sw and eqh_lvl is not None and h > eqh_lvl:
        eqh_sw = True; bEv = "Equal highs"

    if sEv:
        ssl = dict(bar=i, name=sEv, lo=l, loB=i, hi=(h if c > o else c))
    elif ssl:
        if l < ssl['lo']:
            ssl = dict(bar=i, name=ssl['name'], lo=l, loB=i, hi=(h if c > o else c))
        else:
            ssl['hi'] = max(ssl['hi'], h)
    if bEv:
        bsl = dict(bar=i, name=bEv, hi=h, hiB=i, lo=(l if c < o else c))
    elif bsl:
        if h > bsl['hi']:
            bsl = dict(bar=i, name=bsl['name'], hi=h, hiB=i, lo=(l if c < o else c))
        else:
            bsl['lo'] = min(bsl['lo'], l)

    # FVG birth + displacement
    bull_gap = bear_gap = False
    if i >= 2:
        bull_gap = l > BARS[i - 2][2] and (l - BARS[i - 2][2]) >= 0
        bear_gap = h < BARS[i - 2][3] and (BARS[i - 2][3] - h) >= 0
    body = abs(c - o)
    avg_body.append(body)
    if len(avg_body) > 20:
        avg_body.pop(0)
    ab2 = sum(avg_body[:-2]) / len(avg_body[:-2]) if len(avg_body) > 2 else body
    disp_ok = i >= 2 and abs(BARS[i - 1][4] - BARS[i - 1][1]) >= 1.3 * ab2
    if bull_gap or bear_gap:
        fvg.append(dict(t=(l if bull_gap else BARS[i - 2][3]),
                        b=(BARS[i - 2][2] if bull_gap else h),
                        bull=bull_gap, inv=False))
    evBI = evSI = None
    for f in fvg:
        if not f['inv']:
            if not f['bull'] and c > f['t']:
                f['inv'] = True
                if evBI is None: evBI = (f['t'] + f['b']) / 2
            elif f['bull'] and c < f['b']:
                f['inv'] = True
                if evSI is None: evSI = (f['t'] + f['b']) / 2
    dead = [f for f in fvg if (f['inv'] and ((not f['bull'] and c < f['b']) or (f['bull'] and c > f['t'])))
            or (not f['inv'] and ((f['bull'] and c < f['b']) or (not f['bull'] and c > f['t'])))]
    for f in dead:
        fvg.remove(f)
    if len(fvg) > 20:
        del fvg[:len(fvg) - 20]

    ctx.append(dict(t=t, i=i, h=h, l=l, o=o, c=c, mid=mid, rth_prev=rth_prev, rth50=rth50,
                    aH=aH, aL=aL, lH=lH, lL=lL, aHsw=aHsw, aLsw=aLsw, lHsw=lHsw, lLsw=lLsw,
                    eqh_lvl=eqh_lvl, eqh_sw=eqh_sw, eql_lvl=eql_lvl, eql_sw=eql_sw,
                    ssl=ssl, bsl=bsl, bull_gap=bull_gap, bear_gap=bear_gap, disp_ok=disp_ok,
                    evBI=evBI, evSI=evSI, h1=h1fvg_at(t), piv_h=piv_h[i - 3] if i >= 3 else None,
                    piv_l=piv_l[i - 3] if i >= 3 else None))

def run(cfg):
    """cfg: 'A' 0830-1100 or 'B' 0200-1100. Returns list of plan dicts."""
    win0, win1 = (8.5, 11.0) if cfg == 'A' else (2.0, 11.0)
    plans = []
    state = 0
    day = dict(N=0, L=0)
    lastX = -9
    cur = None
    cur_day = None
    for i in range(N):
        q = ctx[i]
        t = q['t']
        d = t.date()
        if d != cur_day:
            cur_day = d
            day = dict(N=0, L=0)
            runHi = runLo = None
            if state >= 1:                      # new day: drop stale plan
                state = 0
                cur = None
        runHi = q['h'] if runHi is None else max(runHi, q['h'])
        runLo = q['l'] if runLo is None else min(runLo, q['l'])
        hmf = t.hour + t.minute / 60.0
        in_win = win0 <= hmf < win1
        lunch = 12 <= t.hour < 13

        # ---------------- management
        if state == 1 and i > cur['bar']:
            fill = q['l'] <= cur['e'] if cur['long'] else q['h'] >= cur['e']
            ran1 = q['h'] >= cur['t1'] if cur['long'] else q['l'] <= cur['t1']
            if ran1 and not fill:
                state, cur = 0, None
            elif fill:
                state = 2
                day['N'] += 1
                stop_hit = (q['l'] <= cur['s']) if cur['long'] else (q['h'] >= cur['s'])
                if stop_hit:
                    cur['exit'] = ('stop', cur['s']); finish(q, cur, False, day); state, cur, lastX = 0, None, i
            elif i - cur['bar'] >= EXPB or (lunch and state == 1):
                state, cur = 0, None
        elif state == 2:
            st = (q['l'] <= cur['s']) if cur['long'] else (q['h'] >= cur['s'])
            t1 = (q['h'] >= cur['t1']) if cur['long'] else (q['l'] <= cur['t1'])
            if st:
                cur['exit'] = ('stop', cur['s']); finish(q, cur, False, day); state, cur, lastX = 0, None, i
            elif t1:
                state = 3
                cur['r1'] = abs(cur['t1'] - cur['e']) / cur['rk']
                cur['s'] = cur['e']                    # breakeven
                t2 = (q['h'] >= cur['t2']) if cur['long'] else (q['l'] <= cur['t2'])
                if t2:
                    cur['exit'] = ('tp2', cur['t2']); finish(q, cur, True, day); state, cur, lastX = 0, None, i
            elif lunch:
                cur['exit'] = ('lunch', q['c']); finish(q, cur, False, day); state, cur, lastX = 0, None, i
        elif state == 3:
            st = (q['l'] <= cur['s']) if cur['long'] else (q['h'] >= cur['s'])
            t2 = (q['h'] >= cur['t2']) if cur['long'] else (q['l'] <= cur['t2'])
            if st:
                cur['exit'] = ('be/trail', cur['s']); finish(q, cur, True, day); state, cur, lastX = 0, None, i
            elif t2:
                cur['exit'] = ('tp2', cur['t2']); finish(q, cur, True, day); state, cur, lastX = 0, None, i
            elif lunch:
                cur['exit'] = ('lunch', q['c']); finish(q, cur, True, day); state, cur, lastX = 0, None, i
            else:
                pl, ph = q['piv_l'], q['piv_h']
                if cur['long'] and pl is not None and pl - BUFPX > cur['s'] and pl < q['c']:
                    cur['s'] = pl - BUFPX
                elif not cur['long'] and ph is not None and ph + BUFPX < cur['s'] and ph > q['c']:
                    cur['s'] = ph + BUFPX

        if state >= 1:
            continue

        # ---------------- new plans
        if not in_win or day['N'] >= 2 or day['L'] >= 2 or i - lastX <= 3:
            continue
        ssl, bsl = q['ssl'], q['bsl']
        side = None
        sRecent = ssl is not None and i - ssl['bar'] <= RECB
        bRecent = bsl is not None and i - bsl['bar'] <= RECB
        lFVG = q['bull_gap'] and q['disp_ok'] and ssl is not None and i - 2 >= ssl['loB']
        lIF = q['evBI'] is not None and ssl is not None and i > ssl['loB']
        sFVG = q['bear_gap'] and q['disp_ok'] and bsl is not None and i - 2 >= bsl['hiB']
        sIF = q['evSI'] is not None and bsl is not None and i > bsl['hiB']
        if sRecent and (lFVG or lIF):
            side = True
        elif bRecent and (sFVG or sIF):
            side = False
        if side is None:
            continue
        if side:
            e = (q['l'] + BARS[i - 2][2]) / 2 if lFVG else q['evBI']
            s = ssl['lo'] - BUFPX
            rk = e - s
            t1 = ssl['hi'] - PADPX
            cands = []
            if q['rth_prev'] and q['rth_prev'] > t1: cands.append(q['rth_prev'])
            if not q['eqh_sw'] and q['eqh_lvl'] and q['eqh_lvl'] > t1: cands.append(q['eqh_lvl'])
            if q['lHsw'] == 0 and q['lH'] and q['lH'] > t1: cands.append(q['lH'])
            if q['aHsw'] == 0 and q['aH'] and q['aH'] > t1: cands.append(q['aH'])
            dd = t.date() - dt.timedelta(days=1)
            if dd in DAYH and DAYH[dd] > t1 and runHi < DAYH[dd]:
                cands.append(DAYH[dd])
            t2 = (min(cands) - PADPX) if cands else e + 2.0 * rk
        else:
            e = (q['h'] + BARS[i - 2][3]) / 2 if sFVG else q['evSI']
            s = bsl['hi'] + BUFPX
            rk = s - e
            t1 = bsl['lo'] + PADPX
            cands = []
            if q['rth_prev'] and q['rth_prev'] < t1: cands.append(q['rth_prev'])
            if not q['eql_sw'] and q['eql_lvl'] and q['eql_lvl'] < t1: cands.append(q['eql_lvl'])
            if q['lLsw'] == 0 and q['lL'] and q['lL'] < t1: cands.append(q['lL'])
            if q['aLsw'] == 0 and q['aL'] and q['aL'] < t1: cands.append(q['aL'])
            dd = t.date() - dt.timedelta(days=1)
            if dd in DAYL and DAYL[dd] < t1 and runLo > DAYL[dd]:
                cands.append(DAYL[dd])
            t2 = (max(cands) + PADPX) if cands else e - 2.0 * rk
        if rk < 5 or rk > 35:
            continue
        r1 = abs(t1 - e) / rk
        r2 = abs(t2 - e) / rk
        ok_order = (t1 > e and t2 > t1) if side else (t1 < e and t2 < t1)
        if not ok_order or r1 < 1.0 or r2 < 2.0:
            continue
        h1 = q['h1']
        in1H = h1 is not None and ((side and h1[0] == 'bull') or (not side and h1[0] == 'bear')) and h1[2] <= e <= h1[1]
        nw = False
        grade = 'A' if in1H else ('B' if (ssl or bsl) else 'C')
        cur = dict(bar=i, long=side, e=e, s=s, s0=s, rk=rk, t1=t1, t2=t2, day=d,
                   time=t, sweep=(ssl if side else bsl)['name'], grade=grade, in1H=in1H)
        state = 1
        plans.append(cur)
    return [p for p in plans if 'exit' in p or True]

def finish(q, cur, half, day):
    e, s, t1 = cur['e'], cur['s'], cur['t1']
    kind, px = cur['exit']
    dirS = 1 if cur['long'] else -1
    r1 = cur.get('r1', abs(t1 - e) / cur['rk'])
    if half:
        rr = 0.5 * r1 + 0.5 * (px - e) * dirS / cur['rk']
    else:
        rr = (px - e) * dirS / cur['rk']
    cur['R'] = round(rr - 1.0 / (cur['rk'] * 2.0), 2)
    if cur['R'] < 0:
        day['L'] += 1

PLANS = {'A': run('A'), 'B': run('B')}
json.dump({k: [{kk: (vv.isoformat() if isinstance(vv, (dt.date, dt.datetime)) else vv) for kk, vv in p.items()} for p in v]
           for k, v in PLANS.items()}, open('crosscheck_plans.json', 'w'), indent=1)
for cfg in 'AB':
    rs = [p['R'] for p in PLANS[cfg] if 'R' in p]
    print(f"cfg {cfg}: plans {len(PLANS[cfg])}, completed {len(rs)}, total R {sum(rs):+.2f}, "
          f"avg {sum(rs)/len(rs) if rs else 0:+.2f}")
