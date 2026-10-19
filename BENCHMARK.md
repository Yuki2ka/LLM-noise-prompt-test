# NPBench — automatic benchmark for LLM robustness to input noise

Working name. Measures how model performance degrades as prompts get typos/noise at a
controlled character rate, on a **fixed frozen noisy corpus**, with **deterministic
grading** (no LLM judge). Output: one comparable score per model + the shape of its
failure curve.

## 1. Where this sits vs existing work

- Brittlebench (arXiv 2603.13285): semantics-preserving prompt perturbations, variance
  decomposition; shows clean-input evals overestimate performance and rankings can flip
  under noise.
- MulTypo (arXiv 2510.09536): realistic keyboard typos on MMLU/GSM-style tasks, 18 models;
  word-level typo rate.
- RRB (arXiv 2604.08571): 13 deterministic structural perturbations on AIME; some open
  models drop to 0% (cliff failures).
- LANTERN (arXiv 2609.07309): per-perturbation-class drops on MCQ.
- Text Uncanny Valley (arXiv 2605.07186): *non-monotonic* (U-shaped) degradation under
  word fragmentation — a direct argument for measuring the full curve, not endpoints.
- "When Is Noise Response Universal?" (arXiv 2608.26319): tokenization is a hidden
  variable — the same character-level noise hits different tokenizers differently.

Gap NPBench fills: a character-level, seeded, versioned noisy corpus (exactly what this
repo's tools produce), purpose-built items that are automatically gradable with *partial
credit*, and a curve-level metric system instead of "average drop at one noise level".

## 2. Metric system

Principle: robustness is a **function** — accuracy P(α) as a function of noise level α.
A single number must preserve the shape of that function, and the full curve must stay
reportable.

Definitions
- **α** — fraction of content characters in the prompt that are perturbed, each by
  exactly one operation. Same semantics as the slider in `index.html` / `b.html`.
  Range [0, 0.5]; at 0.5 the prompt is barely recognizable.
- **Item i** — a prompt with a deterministic grader producing a score s ∈ [0, 1]
  (partial credit allowed).
- **Realization r** — one seeded draw of *which* characters get perturbed. R = 5 per
  (item, α).
- **s̄(i, α)** — mean score over the R realizations.
- **Conditional curve (primary)**: I(M) = items the model solved clean
  (s̄(i, 0) ≥ 0.8). P_M(α) = mean of s̄(i, α) over I(M). Conditioning on clean
  solvability separates "cannot do the task" from "loses it under noise".

Metrics (all derived from P_M plus the raw per-realization scores):

| # | Metric      | Formula (levels α = 0…0.5)            | Captures |
|---|-------------|---------------------------------------|----------|
| 1 | P0          | P_M(0)                                | clean competence (context, not a robustness score) |
| 2 | **NRS**     | 100 · ∫₀^0.5 P(α) dα / P0 (trapezoid) | headline: fraction of clean performance kept across the whole noise range (robustness area) |
| 3 | α@10        | min α with P(α) ≤ P0 − 0.10, else ">0.50" | tolerance: how much noise before losing 10 points |
| 4 | α@½         | min α with P(α) ≤ P0 / 2, else ">0.50"  | half-life of accuracy |
| 5 | Res         | P(0.5) / P0                           | what remains at severe noise |
| 6 | Slope       | (P(0.1) − P(0.4)) / 0.03              | fragility: accuracy points lost per 10% more chars noised |
| 7 | Cliff       | max over adjacent levels of P(αₖ) − P(αₖ₊₁), clamped ≥ 0 | abruptness of failure; a smooth decline is more trustworthy than a cliff |
| 8 | Valley      | count of interior local minima of P   | non-monotonicity (uncanny-valley behavior) |
| 9 | σ / Q10     | stdev & 10th pct of per-realization scores at α = 0.5 | run-to-run variance under noise; tail reliability |
| 10 | CR(α)       | per requirement: fraction of items where the requirement still holds at α | constraint retention (code items): *which* requirements the noise kills |
| 11 | Op profile  | P_M,o(0.3) with single operator o active | sensitivity fingerprint: swap vs delete vs space vs replace |

Reading the leaderboard: **P0 × NRS** is a 2-D map — "can it do the task" × "does it
keep doing it". α@10 / α@½ / Cliff / Valley explain *how* it fails. A model that is
weaker clean but flatter may top the robustness column; that is intended.

Reference implementation: `noisebench.py` (Python 3, stdlib only).
`python3 noisebench.py --demo` runs a 3-model synthetic example.

## 3. Corpus (v1: 200 items)

| Family | Count | Tests | Auto-grader |
|---|---|---|---|
| A · Code | 50 (25 short / 25 medium) | understanding → executable spec | hidden unit tests; partial credit = weighted fraction of tests passing (10 s sandbox) |
| B · Factual QA | 40 | knowledge retrieval through noise | exact match vs alias list after normalization (case / whitespace / punctuation / units) |
| C · Numeric | 30 | arithmetic & reasoning with numbers | number extraction (int, decimal, fraction, %) + relative tolerance 1e-2 |
| D · Needle reading | 30 | planted unique fact (name / id / number) inside a paragraph; "find it" | exact match on the needle |
| E · Instruction / format | 30 | noise in the *instruction* (JSON keys, "answer in one sentence", "output only a number") | structural validator + content check |
| F · Fidelity (control) | 20 | "repeat this string exactly" — a *different* skill (verbatim copy, not comprehension) | 1 − normalized Levenshtein distance |

- F is reported separately and **excluded from NRS**: a model that silently
  auto-corrects typos is rewarded on A–E but punished on F. Both behaviors are
  legitimate; they must not be conflated.
- Difficulty calibration: run a candidate pool (≥ 400 items) at α = 0 on 2–3 reference
  models; keep items with clean pass rate in [0.6, 0.95]. Too-easy items leave no room
  to measure degradation; too-hard items confound difficulty with robustness.
- Code items carry 4–8 tests, including the edge cases the prompt names — the
  prompt's wording of each constraint is what the noise attacks, and each constraint
  must be a separately scored test for CR(α).
- Item metadata (JSON): `id`, `family`, `difficulty`, `prompt`, `key_spans` (char
  ranges of requirement-critical text: numbers, names, constraint phrases), grader
  spec, aliases / tolerance / format, reference clean results.

## 4. Noise protocol

Operators (v1): the tool's three — **adjacent swap, letter delete, space insert** —
plus **letter replace** (keyboard-neighbor, MulTypo-style) and **letter duplicate**.
Each targeted character gets exactly one operation, drawn uniformly from the enabled
set; α = #targets / #content characters (newlines excluded, as in the tool).

Modes
- **Uniform** — targets drawn uniformly at random (the tool's current behavior).
  Primary condition.
- **Targeted** — 50% of the noise budget concentrated inside `key_spans`, 50%
  elsewhere. Stress condition; reported as a separate NRS_t.

Determinism & freezing
- seed = sha256(item_id ‖ α ‖ op_set ‖ r); fixed PRNG (mulberry32 in JS,
  `random.Random` in Python), cross-checked with a shared test vector so the web tool
  and the harness emit *identical* noise for the same seed.
- The full noisy corpus is generated **once** and committed as a versioned JSON
  artifact (NPBench v1.0, content hash pinned in this file). Every lab, every model
  sees exactly the same strings — this is what makes cross-lab comparison possible,
  and it is the one thing the current tool (fresh random per click) does not provide.

## 5. Grading

All deterministic; no LLM judge enters NRS.
- **Code**: run generated code against hidden tests in a subprocess sandbox (10 s
  timeout, no network). Score = Σ weight(passed) / Σ weight.
- **Exact match**: normalize (case, whitespace, punctuation, units), then compare
  against the alias list.
- **Numeric**: regex number extraction (int / decimal / fraction / %), relative
  tolerance.
- **Format**: JSON parse + key-set check, sentence count, "number only", etc.
- **Fidelity**: Levenshtein on normalized strings.
- **LLM judge**: optional secondary metric for open-form items only; never in NRS.

## 6. Evaluation protocol

- Sampling: temperature 0, fixed system prompt, max_tokens 1024 (2048 for code).
  Optional secondary condition: majority of 3 at temperature 0.5.
- Realizations: R = 5 per (item, α) — averages over *where* the noise lands; σ is
  reported so "robust on average" cannot hide occasional catastrophic failures.
- Confidence: 1000 bootstrap resamples over items for each level and for NRS.
- Versioning: corpus version + artifact hash + model card per run (name, weights,
  sampling config). Raw results stored as (model, item, α, r) tuples so any metric
  can be re-aggregated later.
- Cost: 200 items × 6 levels × 5 realizations = 6,000 generations per model;
  operator profile + ~800; targeted mode + ~3,000. ≈ 10k calls per model — a few GPU
  hours on 1–2 GPUs for a 27B-class model, negligible for API frontier models.

## 7. Reporting & failure taxonomy

Per model: P0, NRS, α@10, α@½, Res, Slope, Cliff, Valley, σ@0.5, Q10@0.5, plus
per-family and per-operator breakdowns and the CR(α) constraint-retention heatmap.

Failure types to look for (all observed in the literature, expected here):
- **Slope** — uniform brittleness, degrades smoothly at every level.
- **Cliff** — works until a threshold, then collapses (RRB: some open models hit 0%
  under structural noise).
- **Constraint-selective** — specific requirements die first (e.g. the "ignore case"
  clause) while the core survives; only visible via CR(α).
- **Non-monotonic** — performance recovers at high noise (U-shaped valley).

Illustrative leaderboard (synthetic, from `python3 noisebench.py --demo`):

```
model       items  P0     NRS   a@10  a@half  Res   Slope  Cliff  Valley  Sig@0.5  Q10@0.5
----------  -----  -----  ----  ----  ------  ----  -----  -----  ------  -------  -------
A-flat      59     0.931  85.4  0.20  >0.50   0.7   5.6    0.06   0       0.055    0.57
B-cliff     59     0.911  70.4  0.20  0.40    0.4   13.8   0.286  0       0.063    0.29
C-low-flat  38     0.867  87.6  0.30  >0.50   0.75  4.3    0.049  0       0.047    0.6
```

Synthetic data from `python3 noisebench.py --demo`. Note the point of the metric
system: C is the weakest clean (P0 0.867) but the most robust (NRS 87.6, keeps 10
points until 30% of characters are noised); B is strong clean but has a cliff at
30% noise (Cliff 0.286, half-life 0.40) — a single "average drop" number would not
distinguish them the way P0 × NRS × Cliff do.

## 8. Roadmap (in this repo)

1. Extract the noise engine into a shared deterministic module (JS for the web pages
   + Python for the harness); verify identical output on a pinned test vector.
2. Author corpus v0: 40 items, seeded from the four prompts in `index.html` /
   `b.html`, each with a grader spec.
3. Grader runner (Python, sandboxed test execution) reading the frozen noisy artifact.
4. Metrics pipeline — done: `noisebench.py`.
5. Calibration runs on 2–3 reference models (e.g. Gemma-class 12B, Qwen3 8B/27B, one
   API model); tune family counts and CLEAN_THRESHOLD.
6. Leaderboard page as a new single-file HTML in the style of `index.html` / `b.html`.

## Related work

- https://arxiv.org/abs/2603.13285 Brittlebench
- https://arxiv.org/abs/2510.09536 MulTypo (multilingual typos)
- https://arxiv.org/abs/2604.08571 Robust Reasoning Benchmark
- https://arxiv.org/abs/2609.07309 LANTERN
- https://arxiv.org/abs/2605.07186 The Text Uncanny Valley
- https://arxiv.org/abs/2608.26319 Tokenization as the hidden variable in noise response
