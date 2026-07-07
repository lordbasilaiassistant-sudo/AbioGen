# Backlog — audited issues to fix later

A self-audit of the-pot, captured while a run is in flight. Each entry is
written to become a GitHub issue verbatim once the repo exists (title, labels,
body). Severity: **P1** correctness/integrity · **P2** meaningful gap ·
**P3** polish. None of these block the current experiment; they harden it.

---

## P1 — correctness & research integrity

### 1. Regenerate all committed result artifacts under the fixed RNG
`labels: correctness, reproducibility`
The determinism fix (metric sampling moved to its own RNG so `checkpoint_every`
no longer perturbs dynamics) changed the RNG stream. `results.json`,
`sweep_results.json`, `two_arm.json`, and `replicator_seed2.json` were produced
under a mix of pre/post-fix code, so they are not all reproducible from the
current source. Regenerate every committed artifact with the current code and
re-archive, so "every figure regenerates" is literally true. Note in
`research/` which snapshots predate the fix.

### 2. Guard the determinism fix with a checkpoint-invariance regression test
`labels: test, correctness`
The bug that hid the strong seed-2 replicator was `checkpoint_every` altering the
dynamics. There is no test asserting that two runs with the same seed but
different `checkpoint_every` produce identical soups/trajectories-up-to-sampling.
Add one so the fix can't silently regress. (`pot/soup.py:132` metric_rng.)

---

## P2 — meaningful gaps

### 3. Isolate an *autonomous* replicator (scale to the reference regime)
`labels: science, enhancement`
`pot.hunt` finds real but **contextual** copying (reproduces with the exact
captured partner, 0% against naive partners) and only ~2% emergence vs the
reference's ~40% (arXiv:2406.19108). Diagnosed as soup-size limited (512 vs
~131k tapes). Run at much larger soup size + more epochs; capture soup snapshots
at peak-`repl_rate` epochs (not just end-state) to dissect the actual replicating
pairs; confirm any isolated replicator reproduces against naive partners.

### 4. Wire two-arm, hunt, and the sweep fire-grid into the static site
`labels: frontend`
`web/build_site.py` predates `two_arm.json` and `research/hunt_results.json` and
does not render them. The showcase `index.html` therefore omits our richest
findings (WILD vs TENDED, emergence-rate-by-regime, isolated-replicator table,
sweep fire-grid). Extend `build_site.py` to embed and visualize them.

### 5. Persist sweep/hunt results incrementally
`labels: robustness`
`pot.sweep` and `pot.hunt` only write the aggregate JSON at the end; a long run
that is killed loses every completed run. Flush per-run results to disk as they
complete (append-only JSONL) so partial runs are recoverable.

### 6. Derive firing thresholds from the control distribution, not constants
`labels: honesty, science`
`MOTIF_FLOOR`, `MOTIF_MARGIN`, `NEAR_MARGIN`, etc. are hand-tuned constants and
are soup-size dependent (the motif noise floor scales with soup size). Replace
with thresholds derived statistically from the scrambled control's own
seed-to-seed distribution (e.g. real must exceed control mean + k·sd), so the
honesty gate self-calibrates per regime.

### 7. Honest rungs in the live dashboard (running scramble baseline)
`labels: frontend, honesty`
`web/live.html` rung "reached" flags use absolute thresholds with no control, so
the live view can imply a rung crossed when the scrambled control would also
cross. Stream a lightweight running scramble baseline alongside the showcase and
gate the live rung lamps on real-vs-control, matching the research pipeline.

### 8. Test `pot.live` and the `on_checkpoint` callback
`labels: test`
The live streamer and the new `run_soup(on_checkpoint=...)` path have no test.
Add a smoke test asserting the callback fires, `web/live.json` is valid, and the
grid/rungs/trajectory fields are well-formed.

---

## P3 — polish & performance

### 9. Remove dead `SoupRun.to_json`
`labels: cleanup`
`pot/soup.py:119` `to_json` is unused and has a confused `asdict` vs `__dict__`
branch. Remove it (or fix and use it consistently).

### 10. Cheapen the `near_repl` probe
`labels: performance`
`_best_shift_similarity` is O(K·L²) (all cyclic shifts) per checkpoint and
dominates checkpoint cost, yet `near_repl` is excluded from firing (confounded).
Sample a few shifts or drop to O(K·L); it is only a watch line.

### 11. Return a flat buffer from Rust `run_batch`
`labels: performance`
`rust/src/lib.rs` allocates a `PyBytes` per tape and the Python side does
`b"".join(...)`. For large soups this churns memory. Return one flat buffer +
lengths (or write into a preallocated array) to cut allocations.

### 12. Thicken the extinction-anchor visual without weakening it
`labels: frontend, enhancement`
The null world goes extinct at gen 0, so the anchor chart is structured-climb vs
a single red dot. Model a short visible decline (metabolic/soft-floor dynamics)
that still guarantees extinction every seed, for a clearer honesty visual.

### 13. Docs: CONTRIBUTING + citation/license footer on the site
`labels: docs`
Add a CONTRIBUTING with the reproduce/verify workflow, and a footer on the
generated site citing arXiv:2406.19108 and the MIT license.
