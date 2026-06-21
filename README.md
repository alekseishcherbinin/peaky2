# mascope-peak-assign — developer / iteration guide

> **Validating this on your own Mascope data? Start with [QUICKSTART.md](QUICKSTART.md).**

From-scratch, test-driven successor to `mascope-formula-assignment`. This dir is
the canonical home: edit here, run tests here, ship here. (An earlier scratch
copy may still exist at `~/mascope-assign` — ignore/delete it; this is the one.)

## Layout

```
mascope-peak-assign/
  SKILL.md            invocable manifest + full usage (read this first)
  ROADMAP.md          the agreed next-step quality work (calibration, carbon clamp, ...)
  README.md           this file
  mascope_assign/     the package (see SKILL.md module map) — single-sample assign
                      + the batch pipeline: sampling / assign_batch / cluster /
                      analyte_viz (full VK) / pdf_report
  tests/              one test_<module>.py per module (26 files) + fixtures/match_tree.json
  scripts/
    run_assignment.py one-shot: pipeline -> csv/xlsx/md/json/html
    gka_widget.py     standalone interactive rotating-GKA from a ledger CSV
```

For a whole batch (5 time-spaced + max-TIC samples merged → clustering → PDF
report), see the "Representative-sample batch pipeline" section of SKILL.md and the
reference drivers in `~/mascope-output/orange-assign/` (run_orange / run_clusters /
run_vankrevelen / run_report).

## Install & run

```bash
pip install -e .                   # pulls mascope-sdk + deps; registers `mascope-assign`
cp .env.example ~/.mascope/.env    # then fill in MASCOPE_URL + MASCOPE_ACCESS_TOKEN

mascope-assign list datasets                              # discover your data
mascope-assign list batches  --dataset "<workspace>"
mascope-assign list samples  --batch "<batch>" --dataset "<workspace>"
mascope-assign assign --sample-id <ID> --reagent Br \
    --height-cutoff 100 --output-dir ~/mascope-output/<name>
```
`--reagent {auto,Br,Ur,NO3,NO3_15N,…}` forces the analyte channels (a positive/sparse sample
otherwise mis-detects as negative). Heavy work runs on the host Python; a Mascope
token is read from `~/.mascope/.env` (or `--env` / `$MASCOPE_ENV`). `~5 min` for a
~1000-peak sample at cutoff 100. (`python3 scripts/run_assignment.py …` still works
as a thin forwarder; `python3 -m mascope_assign …` is equivalent to the script.)

## Test loop

```bash
python3 tests/test_smoke.py          # 2s "install OK" check (no creds, no network)
pytest tests/                        # or: for t in tests/test_*.py; do python3 "$t"; done
```
850+ offline assertions across 31 files, no network. Live smoke for io_mascope:
`MASCOPE_LIVE=1 python3 tests/test_io_mascope.py`. **Rule: every code change
ships with a test; keep the suite green.** Tests use plain asserts and run as
scripts (exit non-zero on failure); each also exposes a validating `test_all`
so `pytest tests/` collects and passes them. CI runs the suite with no creds.

## Design invariants (don't regress)

- One ledger DataFrame, one row per peak; passes only fill/annotate. `ledger.py`
  enforces structural invariants on commit; `ledger.validate()` must return `[]`.
- Mascope is the only scorer (`io_mascope`). Other modules never call the network.
- Chemistry gates are structural (integer-DBE-on-neutral, Senior, O-cap,
  halogens-as-H). See SKILL.md "Chemistry rules".
- Heteroatoms enter the neutral only with positive evidence; relaxed filtering is
  "earned by evidence" (chain membership / isotope confirmation), never default.

## Current status (validation set: the orange-peel batches — full history in ROADMAP.md)

The validation set is the **orange-peeling** experiment in *Aleksei's workspace*, run
end to end through the batch pipeline (representative-sample assign → merge → clustering
→ Van Krevelen → PDF report):

- **Orange peeling (Br⁻ CIMS)** — 80 samples / ~96 min. 6 representative files
  (5 time-spaced + max-TIC) → **merged 502 M0 (402 Identified / 100 Candidate)**,
  ~4× the per-file coverage.
- **Orange peeling (Ur⁺ CIMS)** — 81 samples / ~97 min. 6 representative files →
  **merged 1319 M0 (1065 Identified / 254 Candidate)**; the positive-mode NH₄→amine
  co-variation gate is applied at merge.

Reproduce with `mascope-assign batch --batch "<your batch>" --reagent <Br|Ur|NO3|NO3_15N|auto>`
(see [QUICKSTART.md](QUICKSTART.md)); regenerate the figures + report offline with
`mascope-assign report`. The full pipeline (6 passes + audits, the siloxane / composite /
isotope-envelope / ladder logic, tiering, calibration) and its development history live in
`ROADMAP.md` and `SKILL.md`.

## Performance notes

- Cost = `match_compounds` ≈ 3.8 s / 200-formula batch; batches run concurrently
  (`io_mascope.MATCH_WORKERS`). `chemistry._grid_cached` memoises grid
  enumeration (a missing cache once caused a 60× regression).
- Per-pass timing is logged by `assign._safe` and stored in the manifest.
- `cheminfo` is off by default (flaky/slow; grid is the primary enumerator).
