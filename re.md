think can we invent some metrics that good describe how good LLM against input noise. to be possible compare.

what may be the automatic benchmark for it? similar to LLM intelligence benchmarks.


Yes — and I've turned the idea into a concrete spec + working reference implementation in the repo. The core principle: **robustness is a function P(α) — accuracy vs. noise level — not a number.** Any benchmark that reports "average drop at one noise level" (what MulTypo/Brittlebench/RRB all do) throws away the shape of failure, and that shape is exactly what distinguishes models.

## The metric system (11 metrics, 1 headline)

| Metric | Formula | Captures |
|---|---|---|
| **P0** | P(0) | clean competence (context, not robustness) |
| **NRS** | 100 · ∫₀^0.5 P(α)dα / P0 | **headline**: fraction of clean performance kept across the whole noise range |
| α@10 / α@½ | first α where P drops 10 pts / halves | "tolerance" & half-life — easy to communicate |
| Res | P(0.5)/P0 | what remains when the prompt is half-noised |
| Slope | (P(0.1)−P(0.4))/0.03 | fragility: points lost per 10% more chars noised |
| Cliff / Valley | max adjacent drop / local minima | abrupt collapse vs. smooth decline; non-monotonic recovery (the "uncanny valley" is real — measured by a U-curve on word fragmentation) |
| σ / Q10 at 0.5 | stdev & 10th pct of per-realization scores | "robust on average" hiding catastrophic tail failures |
| CR(α) | per-requirement retention | which *specific constraint* the noise kills ("ignore case" dies first) — the partial-credit view |
| Op profile | P(0.3) per single operator | swap vs delete vs space sensitivity fingerprint |

Two design decisions that make it **comparable**:
1. **Condition on clean solvability** — P(α) is computed only over items the model solved at α=0. Otherwise a drop reflects difficulty, not brittleness.
2. **P0 × NRS is a 2-D map**, not a ranking: a weaker-clean but flat model and a strong-clean but cliff-y model are different things, and the numbers say which.

## The automatic benchmark

- **Corpus**: 200 purpose-built items in 6 families, all with **deterministic graders — no LLM judge**: code (hidden unit tests, partial credit = weighted test pass fraction), factual QA (normalized exact match + aliases), numeric (parse + tolerance), needle-in-paragraph (exact match), instruction/format (JSON/sentence-count validators), and a *fidelity control* ("repeat exactly" — measures a different skill, reported separately so "silently autocorrects" isn't conflated with "robust").
- **Noise**: exactly your tool's semantics — α = fraction of characters perturbed, each by one op (swap/delete/space, + replace/duplicate later), seeded `sha256(item‖α‖ops‖r)`, 5 realizations per (item, α). The whole noisy corpus is generated **once and frozen as a versioned JSON artifact** — every lab, every model sees identical strings. That's the missing piece vs. your current "fresh random per click."
- **Protocol**: temperature 0, fixed system prompt, bootstrap CIs, ~6k generations/model (+ targeted-noise and per-operator variants ≈ 10k total) — a few GPU-hours on a 27B-class model.
- **Calibration**: items kept only if reference models pass 60–95% clean, so the curve has room to fall.

## What's in the repo now

- **`BENCHMARK.md`** — full spec: metric formulas, corpus design, noise protocol, grading, cost, failure taxonomy, roadmap (extract your noise engine into a shared deterministic JS+Python module → 40-item v0 corpus → grader runner → calibration → leaderboard page in your single-file-HTML style).
- **`noisebench.py`** — reference implementation of all the core metrics (stdlib only); `python3 noisebench.py --demo` reproduces:

```
model       items  P0     NRS   a@10  a@half  Res   Slope  Cliff  Valley  Sig@0.5  Q10@0.5
A-flat      59     0.931  85.4  0.20  >0.50   0.7   5.6    0.06   0       0.055    0.57
B-cliff     59     0.911  70.4  0.20  0.40    0.4   13.8   0.286  0       0.063    0.29
C-low-flat  38     0.867  87.6  0.30  >0.50   0.75  4.3    0.049  0       0.047    0.6
```

C is weakest clean but most robust; B is strong clean but has a cliff at 30% — a single "average drop" number can't tell those apart, this one can.

Positioning vs. prior work (cited in the doc): Brittlebench shows clean evals overestimate and rankings *flip* under noise; RRB shows cliff failures down to 0%; the tokenizer is a hidden variable (same char-noise ≠ same token-noise across models — documented as a caveat).

Want me to go the next step — port your noise engine into a deterministic JS/Python module with a shared test vector, and draft the 40-item v0 corpus with grader specs seeded from your four prompts?