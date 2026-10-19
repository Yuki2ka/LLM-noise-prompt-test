#!/usr/bin/env python3
# noisebench.py — NPBench metrics, reference implementation (stdlib only).
#
# Input JSON, one file per model run:
# {
# 	"model": "name",
# 	"levels": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],   // optional, this default
# 	"scores": { "<item>": { "0.0": [s, s, ...], "0.1": [...] } },  // one score per noise realization, [0,1]
# 	"clean_ok": { "<item>": true }              // optional override of the clean-solvability filter
# }
#
# Usage:
# 	python3 noisebench.py run.json [more.json ...]
# 	python3 noisebench.py --demo

import json
import math
import random
import sys

ALPHA_MAX = 0.5
CLEAN_THRESHOLD = 0.8
DEFAULT_LEVELS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

def _k(x):
	return str(round(float(x), 2))

def mean(xs):
	return sum(xs) / len(xs)

def _is_clean_ok(iid, by_level, clean_ok):
	clean = by_level.get(_k(0.0), [])
	if not clean:
		return False
	if clean_ok is not None and iid in clean_ok:
		return bool(clean_ok[iid])
	return mean(clean) >= CLEAN_THRESHOLD

def p_curve(scores, levels, clean_ok=None):
	# conditional accuracy curve: mean over realizations, then over items solved clean
	items = []
	for iid, by_level in scores.items():
		if not _is_clean_ok(iid, by_level, clean_ok):
			continue
		if all(by_level.get(_k(a)) for a in levels):
			items.append({a: mean(by_level[_k(a)]) for a in levels})
	if not items:
		return {}, 0
	return {a: mean([c[a] for c in items]) for a in levels}, len(items)

def ra(curve, levels, alpha_max=ALPHA_MAX):
	# robustness area: mean performance over the noise range (trapezoid)
	area = 0.0
	for a0, a1 in zip(levels[:-1], levels[1:]):
		area += (a1 - a0) * (curve[a0] + curve[a1]) / 2
	return area / alpha_max

def _alpha_at(curve, levels, target):
	for a in levels:
		if curve[a] <= target:
			return f"{a:.2f}"
	return f">{ALPHA_MAX:.2f}"

def stability(scores, levels, clean_ok=None):
	# pooled per-realization scores per level -> (mean, stdev); Q10 at max level
	pools = {a: [] for a in levels}
	for iid, by_level in scores.items():
		if not _is_clean_ok(iid, by_level, clean_ok):
			continue
		for a in levels:
			pools[a].extend(by_level.get(_k(a), []))
	stab = {}
	for a in levels:
		xs = pools[a]
		if xs:
			mu = mean(xs)
			stab[a] = (mu, math.sqrt(sum((x - mu) ** 2 for x in xs) / len(xs)))
		else:
			stab[a] = (None, None)
	xs = sorted(pools[levels[-1]])
	q10 = xs[max(0, int(0.1 * (len(xs) - 1)))] if xs else None
	return stab, q10

def summarize(data, levels=None):
	levels = levels or DEFAULT_LEVELS
	curve, n_items = p_curve(data["scores"], levels, data.get("clean_ok"))
	if not curve:
		return None
	p0 = curve[levels[0]]
	stab, q10 = stability(data["scores"], levels, data.get("clean_ok"))
	cliff = max(0.0, max(curve[a0] - curve[a1] for a0, a1 in zip(levels[:-1], levels[1:])))
	valley = sum(1 for i in range(1, len(levels) - 1)
		if curve[levels[i]] < curve[levels[i - 1]] and curve[levels[i]] <= curve[levels[i + 1]])
	return {
		"model": data.get("model", "?"),
		"items": n_items,
		"P0": round(p0, 3),
		"NRS": round(100 * ra(curve, levels) / p0, 1) if p0 > 0 else 0.0,
		"a@10": _alpha_at(curve, levels, p0 - 0.10),
		"a@half": _alpha_at(curve, levels, p0 / 2),
		"Res": round(curve[levels[-1]] / p0, 2) if p0 > 0 else 0.0,
		"Slope": round((curve[0.1] - curve[0.4]) / 0.03, 1) if 0.1 in curve and 0.4 in curve else None,
		"Cliff": round(cliff, 3),
		"Valley": valley,
		"Sig@0.5": round(stab[levels[-1]][1], 3) if stab[levels[-1]][1] is not None else None,
		"Q10@0.5": round(q10, 2) if q10 is not None else None,
	}

# ---------- demo ----------

def _demo_model(name, p0, frag, cliff_at=None, sd=0.03, seed=0, n_items=60):
	# synthetic model: per-item competence ~ N(p0, 0.08); score decays smoothly
	# with alpha, with an optional abrupt extra drop (cliff) at cliff_at.
	# scores are partial-credit-like (e.g. weighted test-pass fraction)
	rng = random.Random(seed)
	scores = {}
	for i in range(n_items):
		c = min(1.0, max(0.05, rng.gauss(p0, 0.08)))
		by_level = {}
		for a in DEFAULT_LEVELS:
			if cliff_at is None:
				loss = frag * (a / ALPHA_MAX)
			else:
				loss = frag * 0.6 * (a / ALPHA_MAX)
				if a >= cliff_at:
					loss += frag * 0.4
			p = max(0.02, c * (1 - loss))
			by_level[_k(a)] = [round(min(1.0, max(0.0, rng.gauss(p, sd))), 2) for _ in range(5)]
		scores[f"item-{i:03d}"] = by_level
	return {"model": name, "levels": list(DEFAULT_LEVELS), "scores": scores}

DEMO_MODELS = [
	("A-flat", 0.93, 0.30, None, 0.03, 1),
	("B-cliff", 0.90, 0.60, 0.3, 0.06, 2),
	("C-low-flat", 0.82, 0.25, None, 0.02, 3),
]

COLS = ["model", "items", "P0", "NRS", "a@10", "a@half", "Res", "Slope", "Cliff", "Valley", "Sig@0.5", "Q10@0.5"]

def _fmt(v):
	if v is None:
		return "-"
	if isinstance(v, str):
		return v
	return f"{v:g}"

def _print_table(rows):
	widths = {c: max(len(c), *(len(_fmt(r[c])) for r in rows)) for c in COLS}
	print("  ".join(c.ljust(widths[c]) for c in COLS))
	print("  ".join("-" * widths[c] for c in COLS))
	for r in rows:
		print("  ".join(_fmt(r[c]).ljust(widths[c]) for c in COLS))

def main(argv):
	if len(argv) > 1 and argv[1] == "--demo":
		rows = [r for r in (summarize(_demo_model(*m)) for m in DEMO_MODELS) if r]
		_print_table(rows)
		return
	if len(argv) < 2:
		print(__doc__)
		sys.exit(1)
	rows = []
	for path in argv[1:]:
		with open(path) as f:
			r = summarize(json.load(f))
		if r:
			rows.append(r)
	if not rows:
		print("no usable runs found")
		sys.exit(1)
	_print_table(rows)

if __name__ == "__main__":
	main(sys.argv)
