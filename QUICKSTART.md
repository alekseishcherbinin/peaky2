# Quickstart — assign a Mascope batch on your machine

A 5-minute path from a fresh clone to a peak-assignment report on **your own**
Mascope data. For depth see [SKILL.md](SKILL.md); for dev/iteration see
[README.md](README.md).

## 1. Install

```bash
git clone <repo-url> mascope-assign && cd mascope-assign
python3 -m pip install -e .          # pulls mascope-sdk + pandas/numpy/scipy/matplotlib/openpyxl
```
Needs Python ≥ 3.11. Everything (incl. `mascope-sdk`) installs from public PyPI —
no private index, no Mascope account needed just to install.

Confirm the install with the no-network smoke test (≈2 s):

```bash
python3 tests/test_smoke.py          # "50 passed" => imports + deps OK
```

## 2. Credentials

Copy the template to a **project-local `.env`** in the repo root (git-ignored,
found automatically) and fill in your values:

```bash
cp .env.example .env        # then edit .env -> MASCOPE_URL=...  MASCOPE_ACCESS_TOKEN=...
```
Prefer a shared home location? Use `~/.mascope/.env` instead:
```bash
mkdir -p ~/.mascope && cp .env.example ~/.mascope/.env
```
You can also `export MASCOPE_URL=… MASCOPE_ACCESS_TOKEN=…`, or pass `--env
/path/to/.env` to any command. Search order: `--env` / `$MASCOPE_ENV` > repo-root
`.env` (or cwd) > `~/.mascope/.env`. Token: from the Mascope web app.

## 3. Find your data

```bash
mascope-assign list datasets
mascope-assign list batches  --dataset "<your workspace>"
mascope-assign list samples  --batch "<your batch>" --dataset "<your workspace>"
```
`list samples` prints each `sample_item_id`, time and TIC — copy an id for step 4.

## 4. Assign one sample

```bash
mascope-assign assign --sample-id <ID> --reagent <Br|Ur|NO3|auto> \
    --height-cutoff 100 --output-dir ~/mascope-output/<name>
```
`--reagent` forces the analyte channels (a positive/sparse sample otherwise
mis-detects as negative). Writes `<ID>_<UTC>_{ledger.csv, assignments.xlsx,
summary.md, manifest.json, gka.html}`. A ~1000-peak sample takes ≈5 min.

## 5. Assign a whole batch (recommended)

A single averaged file misses analytes present only part of a run, so the batch
flow assigns a representative subset (5 time-spaced + max-TIC) and merges, then
builds cluster figures, a Van Krevelen and a PDF report:

```bash
mascope-assign batch --batch "<your batch>" --dataset "<your workspace>" \
    --reagent <Br|Ur|NO3|auto> --out-dir ~/mascope-output
```
Creates a timestamped run folder `~/mascope-output/<batch-slug>_<UTC>/` with the
merged ledger, per-file ledgers, cluster/VK figures, and `report_<run-id>.pdf`.
A full batch is ≈40 min (mostly the live `match_compounds` calls).

Regenerate the figures + report later **offline** (no re-assignment) with:

```bash
mascope-assign report --run-dir ~/mascope-output/<run-folder> \
    --reagent <Br|Ur|NO3> --ts ~/mascope-output/<run-folder>/<tag>_ts.parquet
```

## Adding your reagent

`Br` (bromide⁻), `Ur` (urea⁺) and `NO3` (nitrate⁻, provisional) are built in. To
add another **without editing the package**, write a small JSON (or TOML) file and
pass `--reagent-config`:

```json
[{"name": "Ac", "label": "Acetate⁻", "polarity": "-",
  "adducts": ["[M+CH3COO]-", "[M-H]-"], "normaliser": "reagent",
  "reagent_ion_re": "C2H3O2-?$", "ranges": "C0-30 H0-50 O0-15",
  "detect_adduct": "[M+CH3COO]-", "aliases": ["acetate"]}]
```
```bash
mascope-assign batch --batch "<batch>" --reagent Ac --reagent-config myreagents.json ...
```

## Troubleshooting

- **`403 / Attention Required`** — Mascope's Cloudflare WAF is rate-limiting you
  after a burst of calls. Wait 15–30 min with no traffic (polling extends it).
- **`401` / token errors** — refresh `MASCOPE_ACCESS_TOKEN` in `~/.mascope/.env`.
- **sample/batch "not found"** — ids go stale when a server copy is renamed;
  re-fetch fresh names with `mascope-assign list`.
- **`ModuleNotFoundError`** — re-run `pip install -e .` (or `pip install -r requirements.txt`).

The CLI catches these at the boundary and prints an actionable hint rather than a
raw traceback.
