#!/usr/bin/env python3
"""Regression: fitment ranking must pick expected kit SKU."""
import re
import subprocess
import sys
import unicodedata

CONN = "postgresql://postgres:Tecbite20$@n8n.yavingos.com:5433/n8ntecbite_db"
ROOF_MAP = {
    "ROOF_D": {"kit": 5, "patterns": ["Normal Roof"]},
    "ROOF_B": {"kit": 6, "patterns": ["Flush Rail", "Flush Rails"]},
    "ROOF_C": {"kit": 7, "patterns": ["Fixed Point", "Fixed Points"]},
}
CASES = [
    ("BMW", "X3", 2018, "ROOF_B", "6007TH"),
    ("Nissan", "Frontier", 2022, "ROOF_D", "5311TH"),
    ("Hyundai", "Tucson", 2019, "ROOF_B", "6013TH"),
    ("Honda", "CR-V", 2017, "ROOF_D", "5108TH"),
    ("Toyota", "Yaris", 2019, "ROOF_D", "5394TH"),
]


def fold(v):
    return "".join(
        c for c in unicodedata.normalize("NFD", str(v or "")) if unicodedata.category(c) != "Mn"
    ).lower()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", fold(s))


def year_range_score(range_raw, year):
    m = re.match(r"(\d{4})\s*-\s*(\d{4}|)?", str(range_raw or ""))
    if not m:
        return 40
    start, end = int(m.group(1)), int(m.group(2)) if m.group(2) else 9999
    if year < start or year > end:
        return -1
    return max(0, 100 - min(end - start + 1, 60))


def model_match_score(parsed, brand, model):
    b, m = fold(parsed["brand"]), fold(parsed["model"])
    bf, mf = fold(brand), fold(model)
    if bf not in b and b not in bf:
        return -1
    pm, qm = norm(parsed["model"]), norm(model)
    if pm == qm:
        return 100
    tokens = [t for t in re.split(r"[\s(,/-]+", m) if len(t) >= 2]
    if any(t == mf or norm(t) == qm for t in tokens):
        return 92
    if re.search(r"(?:^|[\s(,/-])" + re.escape(mf) + r"(?:[\s(,/-]|$)", m):
        return 88
    if pm in qm or qm in pm:
        if (pm.startswith("ix") or re.match(r"^i[a-z0-9]{1,2}$", pm)) and not qm.startswith("i") and len(qm) <= 3:
            return 10
        return 42
    return 0


def parse_caro(line):
    parts = [p.strip() for p in str(line).split(",")]
    if len(parts) < 5:
        return None
    return {"brand": parts[0], "model": parts[1], "yearRange": parts[3], "roofType": parts[4]}


def score_row(sku, title, stock, attrs, brand, model, year, patterns, kit):
    import json

    try:
        data = json.loads(attrs)
    except json.JSONDecodeError:
        return None
    best = -999
    ok = False
    for k, v in data.items():
        if not re.match(r"^Carro\d+$", k, re.I):
            continue
        p = parse_caro(v)
        if not p:
            continue
        ms = model_match_score(p, brand, model)
        ys = year_range_score(p["yearRange"], year)
        if ms < 40 or ys < 0:
            continue
        rf = fold(p["roofType"])
        if not any(fold(rp) in rf or rf in fold(rp) for rp in patterns):
            continue
        ok = True
        best = max(best, ms + ys * 2.5)
    if not ok:
        return None
    return best + (30 if stock == "in_stock" else 10) + (25 if kit and sku.startswith(str(kit)) else -40 if kit else 0) + (10 if "kit" in title.lower() else 0)


def main():
    passed = 0
    for brand, model, year, roof, expected in CASES:
        cfg = ROOF_MAP[roof]
        q = f"""
        SELECT product_sku, title, stock_status, attributes
        FROM tecbite_product_state
        WHERE is_active=true
          AND attributes ILIKE '%{brand}%{model}%'
          AND attributes ILIKE '%{cfg["patterns"][0]}%'
          AND (title ILIKE '%Kit%' OR title ILIKE '%Clamp%' OR title ILIKE '%Flush%')
        LIMIT 80
        """
        out = subprocess.run(["psql", CONN, "-At", "-c", q], capture_output=True, text=True).stdout
        scored = []
        for line in out.strip().split("\n"):
            if "|" not in line:
                continue
            sku, title, stock, attrs = line.split("|", 3)
            s = score_row(sku, title, stock, attrs, brand, model, year, cfg["patterns"], cfg["kit"])
            if s is not None:
                scored.append((s, sku))
        scored.sort(reverse=True)
        top = scored[0][1] if scored else None
        ok = top == expected
        passed += int(ok)
        print(f"{'OK' if ok else 'FAIL'} | {brand} {model} {year} {roof} -> {top} (esp. {expected})")
    print(f"\n{passed}/{len(CASES)} passed")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
