# Roadmap — state after v29 (2026-06-12) and what comes next

## Where the pipeline stands

v32 on the reference sample `<sample-id>` (Br-CIMS, ambient air):
**269 M0 (179 Identified / 90 Candidate) / 58.0% peaks / 90.3% signal
explained, 21/21 flagships, 0 junk, ledger clean.** Run
`python3 scripts/check_flagships.py <ledger.csv>` after ANY change — it
asserts the validated identifications (TFA both channels, hydroxy-acid
ladder, monoterpene rungs + Br partners, silanediol series,
HO2/HNO3/HNO2/HNO4), that every flagship is tier **Identified**, and the
banned junk classes (incl. O>=12 in Identified).

Pipeline shape: pass 0 (known species: contaminant series + atmospheric
acids/radicals, locked, twin-gated) → pass 1 (CHO/CHON backbone + calibration)
→ pass 2 (GKA series) → pass 3 (evidence-opened contaminant families) →
pass 4 (residual: iso-pairs incl. BrCl, deep series, carbon-clamped) →
pass 5 (known-neutral completion: cross-channel + series gaps) →
isotope-physics audit → calibrated mass-gate audit.

## What the residual IS (eliminated dimensions — do not re-chase)

- **Sulfate (SO3)**: dead, 0.06x decoys. **Nitrate (NO3/HNO3/NO2)**: dead,
  0.0–0.1x decoys (the sample's N lives in the small acids, now assigned).
- **Fluorine**: real but small (TFA + telomer); O>6 junk class banned.
- **Silicon**: solved (silanediol ladder, ~115k cps, locked contaminant).
- **Chlorine**: faint (Cl-H at 6x decoys), consistent with the known BrCl
  mixed-halogen family — a thread, not a dimension.
- **The C/H lattice is SOLVED (v30-v32): it was biogenic SOA, not exotic
  organohalogens.** The "proven unsolvable" verdict had a GAP -- it never
  tested the di-bromide *cluster* frame. The bright n_Br=2 peaks are
  mono-/sesquiterpene oxidation products detected as `[M+HBr+Br]-` reagent
  clusters (covalent-Br2 and a Br2 reagent adduct are the SAME ion, so the
  server can't separate them; chemistry + sub-ppm cores pick the cluster).
  Stripping 2 Br gives clean low-DBE cores forming the C2H4 GKA ladder:
  409.0015 = C15H22O3 (0.93 ion score, 5 isotopologues). 10 assigned so far.
- **Still open in the lattice**: ~4 bright n_Br=2 peaks (424.99, 356.93,
  342.91, 574.97) remain unexplained -- their O15/16 monsters are cleared by
  the END mass-gate audit (not the pre-pass-4 carbon clamp), too late to
  re-claim; and the pass-3 cluster-proposal path picks off-by-H2 cores that
  fail the mass gate. Fix next: run the mass-gate demotion pre-pass-4 too, and
  tighten cluster-proposal H-count. The deeper terpene-SOA families beyond
  these are still time-series territory.

## Next big improvements, in priority order

1. **Time-resolved correlation confirmer (THE unlock; user sourcing data).**
   SDK hook exists (`get_peak_timeseries`). Build: co-variation clustering of
   the residual; members of one lattice family must correlate. Resolves
   composites (393/395-style), confirms/kills the 36 Low/Suspect, separates
   inlet contamination (flat) from ambient chemistry (variable), and names
   whole lattices from any single identified member. The ledger already
   carries halogen counts, carbon brackets, and lattice memberships as
   correlation groups.

2. **DONE (this session): tiered reporting — Identified / Candidates /
   Below-assignability** (`tiers.py` + report rewrite). Mechanical rules:
   Low/Suspect, O>=12 lattice monsters, mixed BrCl, eff-score near-ties
   (rescued by cross-channel/series corroboration), close-alternative density
   without corroboration. Same-ion decomposition aliases excluded from
   tie/density counting (adduct-reading policy). Candidate-density is the
   confidence currency (`candidate_density` column; arbitrate now stores 6
   alternatives + winner eff_score/eff_margin/tied). The Candidates sheet
   shows ONE ROW PER CANDIDATE FORMULA. check_flagships now asserts flagship
   tier == Identified and bans O>=12 in Identified. Excel restyled: Summary +
   Read-me legend sheets, frozen headers, autofilters, number formats,
   tier/confidence color chips, per-peak banding on Candidates.

3. **Below-assignability certificates (automate the manual proof).** For each
   bright has-constraints residual peak, run the clamped frame x element
   enumeration and stamp the result into the Unassigned sheet ("searched
   N frames x CHNOSPSi+I, C clamped a–b: zero fits → composite or exotic").

4. **Composite-doublet detection.** Twin ratio deviating >15% from isotope
   prediction → flag "composite: ~N cps hidden component"; marks peaks whose
   clamps are unreliable and feeds the time-series target list.

5. **mu(m/z) mass-dependent calibration.** ~30 z>2 stragglers remain; settle
   drift-vs-wrong-formula (evidence so far says wrong formulas: mixed signs
   at same m/z).

6. **Robustness niceties.** One batch-level re-retry before the (new,
   correct) fail-loud raise in score_candidates bites a whole pass on flaky
   server days; pass-4 `residual_ppm_*` could inherit the calibrated sigma;
   pin the X=76.5 half-integer "C/H lattice" view in the GKA widget; write
   lattice memberships into ledger commentary.

## Standing lessons (encode-don't-remember)

- Every evidence GATE needs a complementary RECOVERY path (TFA: chain gate
  stopped the flood and silently dropped the one real fluorochemical).
- Negative evidence (absent satellite) never overrides independent positive
  evidence (agreeing channel, twin satellite) — peak pickers lose peaks.
- A locked claim must pass self-consistency (own-twin gate) — composites.
- The server's scoring is authoritative; never trust hand ion-mass arithmetic
  (electron-mass sign error cost us TFA's [M-H]- twice).
- Coverage metrics reward fiction; the flagship list + count-based coverage
  are the honest scoreboard.
- GKA rotations: trust rows at integer A(R); verify any non-integer rotation
  (defect-quantum coincidences); half-integer X is a feature (C/H lattice).
