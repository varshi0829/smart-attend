#!/usr/bin/env python3
"""
Add phone and email columns to:
  - Faculty/CSE/teach _cse.csv
  - Faculty/CSE/faculty_class_assignments.csv
  - Faculty/frontend-instructor/faculty_assignments.json

Source: CSE Faculty List 2025-2026 XLS (Sheet1)
"""
import xlrd, csv, json, re, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # smart-attend/Faculty/
ROOT = os.path.dirname(BASE)  # smart-attend/

XLS_PATH   = os.path.join(ROOT, "CSE Faculty List  along with mobile numbers mail ids 2025-2026 (1) (3).xls")
TEACH_CSV  = os.path.join(BASE, "CSE", "teach _cse.csv")
ASSIGN_CSV = os.path.join(BASE, "CSE", "faculty_class_assignments.csv")
JSON_PATH  = os.path.join(BASE, "frontend-instructor", "faculty_assignments.json")


def normalize(s):
    """Lowercase, strip punctuation/spaces to a sorted token set."""
    return set(re.sub(r'[^a-z0-9]', ' ', s.lower()).split())


def jaccard(a, b):
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ── Manual overrides (CSV name → XLS key) ───────────────────────────────────
# Used when fuzzy matching picks the wrong person.
MANUAL = {
    'ms t. durga devi':          'ms t durgadevi',
    'ms. t. durga devi':         'ms t durgadevi',
    'ms t. durgadevi':           'ms t durgadevi',
    'ms. b. pushpa':             'ms pushpa bhupatiraju',
    'ms. g. rama devi':          'ms g ramadevi',
    'ms. s rama devi':           'ms s ramadevi',
    'ms. s. rama devi':          'ms s ramadevi',
    # faculty not in 2025-26 list → leave blank
    'dr. m. indrasena reddy':    None,
    'dr. v. surya narayana reddy': None,
}


# ── 1. Load XLS contact data ─────────────────────────────────────────────────
wb = xlrd.open_workbook(XLS_PATH)
sh = wb.sheet_by_index(0)

contacts = {}   # norm_key (str of sorted tokens) → {phone, email, raw_name}
for r in range(2, sh.nrows):
    raw   = str(sh.cell_value(r, 1)).strip()
    phone = str(sh.cell_value(r, 3)).strip().replace(' ', '')
    email = str(sh.cell_value(r, 4)).strip()
    if not raw:
        continue
    if phone.endswith('.0'):
        phone = phone[:-2]
    k = ' '.join(re.sub(r'[^a-z0-9]', ' ', raw.lower()).split())
    contacts[k] = {'phone': phone, 'email': email, 'raw_name': raw}

print(f"Loaded {len(contacts)} contacts from XLS")


def lookup(name):
    """Return (phone, email) for a teacher name, or ('', '') if not found."""
    low = name.lower().strip()
    # Check manual overrides first
    for pattern, xls_key in MANUAL.items():
        if pattern in low or low in pattern:
            if xls_key is None:
                return '', ''
            c = contacts.get(xls_key, {})
            return c.get('phone', ''), c.get('email', '')

    # Fuzzy match via Jaccard on token sets
    toks = normalize(name)
    best_score, best_key = 0.0, None
    for k in contacts:
        score = jaccard(toks, set(k.split()))
        if score > best_score:
            best_score, best_key = score, k

    if best_score >= 0.45 and best_key:
        c = contacts[best_key]
        return c['phone'], c['email']

    print(f"  [NO MATCH] {name!r} (best={best_score:.2f}, key={best_key!r})")
    return '', ''


# ── 2. Update teach _cse.csv ─────────────────────────────────────────────────
with open(TEACH_CSV, newline='') as f:
    rows = list(csv.DictReader(f))

fieldnames = [k for k in rows[0].keys() if k is not None]
if 'phone' not in fieldnames:
    fieldnames += ['phone', 'email']

updated = []
for row in rows:
    phone, email = lookup(row['Teacher Name'])
    row['phone'] = phone
    row['email'] = email
    # drop None key from trailing commas
    row.pop(None, None)
    updated.append(row)
    print(f"  teach_cse: {row['Teacher Name']!r} -> {phone} / {email}")

with open(TEACH_CSV, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(updated)
print(f"Wrote {len(updated)} rows to {TEACH_CSV}")


# ── 3. Update faculty_class_assignments.csv ──────────────────────────────────
# Build per-teacher contact cache to avoid repeated lookups
teacher_cache = {}

with open(ASSIGN_CSV, newline='') as f:
    arows = list(csv.DictReader(f))

afieldnames = list(arows[0].keys())
if 'phone' not in afieldnames:
    afieldnames += ['phone', 'email']

for row in arows:
    tname = row['teacher_name']
    if tname not in teacher_cache:
        teacher_cache[tname] = lookup(tname)
    row['phone'], row['email'] = teacher_cache[tname]

with open(ASSIGN_CSV, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=afieldnames)
    w.writeheader()
    w.writerows(arows)
print(f"Wrote {len(arows)} rows to {ASSIGN_CSV}")


# ── 4. Update faculty_assignments.json ───────────────────────────────────────
with open(JSON_PATH) as f:
    jdata = json.load(f)

for norm_key, entry in jdata['faculty'].items():
    phone, email = lookup(entry['display_name'])
    entry['phone'] = phone
    entry['email'] = email

with open(JSON_PATH, 'w') as f:
    json.dump(jdata, f, indent=2)
print(f"Updated {len(jdata['faculty'])} faculty entries in {JSON_PATH}")

print("\nDone.")
