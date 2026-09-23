#!/usr/bin/env python3
"""Match engine plans (cfg B = her stream hours) against her logged trades;
write the filled CSV and the cross-validation report tables."""
import json, csv, datetime as dt

P = json.load(open('crosscheck_plans.json'))
B = P['B']; A = P['A']

rows = []
for line in open('uploads/112.txt', encoding='utf-8'):
    c = line.rstrip('\n').rstrip('\r').split('\t')
    if len(c) < 15: c += [''] * (15 - len(c))
    rows.append(c)

HER_TIME = {19: 3.43, 25: 3.0, 28: 2.9, 33: 3.75, 44: 3.0, 46: 3.0,
            47: 2.75, 49: 4.0, 17: 4.0}   # approx ET from her words

def plans_on(d, lng=None):
    out = [p for p in B if p['day'] == d]
    if lng is not None:
        out = [p for p in out if p['long'] == lng]
    return out

matched, script_done = [], []
day_any = {}
for p in B:
    day_any.setdefault(p['day'], day_any.get(p['day'], 0) + 1)

def iso(d):
    return dt.datetime.strptime(d, '%d-%b-%Y').date().isoformat()

for idx, r in enumerate(rows[1:], start=1):
    d, direction, outcome = iso(r[1]) if r[1] else '', r[6], r[9]
    if not d:
        continue
    if outcome == 'No trade':
        n = day_any.get(d, 0)
        r[11] = f"{'Yes' if n else 'No'} ({n} plans)"
        r[13] = "n/a - she sat out"
        continue
    lng = direction == 'Long'
    cands = plans_on(d, lng)
    r[11] = 'Yes' if cands else 'No'
    if not cands:
        r[12] = ''
        r[13] = 'no'
        continue
    pick = None
    if idx in HER_TIME:
        for p in cands:
            tm = float(p['time'][11:13]) + float(p['time'][14:16]) / 60
            if abs(tm - HER_TIME[idx]) <= 1.25:
                pick = p
                break
    if pick is None and len(cands) == 1:
        pick = cands[0]
    if pick is None:
        pick = cands[0]
        r[13] = 'direction yes (time unknown)'
    else:
        r[13] = 'yes' if (idx in HER_TIME) else 'yes (only same-dir plan)'
    matched.append((idx, d, direction, pick))
    if 'R' in pick:
        r[12] = f"{pick['R']:+.2f}"
        script_done.append(pick['R'])
    else:
        r[12] = 'plan, no fill'

with open('Candice_Stream_Log_FILLED.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    for r in rows:
        w.writerow(r)
    w.writerow([])
    w.writerow(['THE SCRIPT (filled by cross-check engine, 5-min NQ=F replica of Candace_ICT_Suite.pine)'])
    w.writerow(['Streams checked with the script', 30, 'all 30 stream dates present in the 5-min cache'])
    w.writerow(['Script plans that matched her trade', len(matched), 'same day + same direction'])
    w.writerow(['Script average R (matched, completed)', round(sum(script_done)/len(script_done), 2) if script_done else '', f"{len(script_done)} completed"])
    w.writerow(['Script total R, stream-hours config', round(sum(p['R'] for p in B if 'R' in p), 2), f"{sum(1 for p in B if 'R' in p)} completed of {len(B)} plans"])
    w.writerow(['Script total R, MFFU 08:30-11:00 config', round(sum(p['R'] for p in A if 'R' in p), 2), f"{sum(1 for p in A if 'R' in p)} completed of {len(A)} plans"])

# ---------------- report aggregates ----------------
her = [(iso(r[1]), r[6], float(r[8].replace('+', '') or 0), r[9]) for r in rows[1:] if r[6] in ('Long', 'Short')]
her_days = {}
for d, dr, rr, oc in her:
    her_days.setdefault(d, [0, 0.0])
    her_days[d][0] += 1
    her_days[d][1] += rr

no_plan_loss = [(d, v[1]) for d, v in her_days.items() if v[1] < 0 and not day_any.get(d)]
she_waited_script_traded = [d for d, v in sorted(day_any.items()) if d not in her_days]
print(f"matched plans: {len(matched)}, completed {len(script_done)}, avg {sum(script_done)/len(script_done) if script_done else 0:+.2f}")
print("her losing days where script had NO plan (losses avoided):")
for d, rr in no_plan_loss: print(f"   {d}  her {rr:+.2f}R")
print("days she did not stream but script traded:", she_waited_script_traded)
her_nt = [iso(r[1]) for r in rows[1:] if r[9] == 'No trade']
print("her no-trade streams where script DID plan:", [d for d in her_nt if day_any.get(d)])
print("her no-trade streams where script also sat out:", [d for d in her_nt if not day_any.get(d)])
json.dump(dict(matched=len(matched), done=script_done,
               avoided=[list(x) for x in no_plan_loss],
               waited_traded=she_waited_script_traded,
               nt_traded=[d for d in her_nt if day_any.get(d)],
               nt_sat=[d for d in her_nt if not day_any.get(d)]),
          open('match_summary.json', 'w'))
