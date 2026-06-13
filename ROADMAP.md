# Roadmap — state after v41 (2026-06-13) and what comes next

## Where the pipeline stands

v41 on the reference sample `<sample-id>` (Br-CIMS, ambient air; batch
"<dataset>", file <instrument> 2025.10.02):
**268 M0 (179 Identified / 89 Candidate) / 60.6% peaks / 90.2% signal
explained, 21/21 flagships, 0 junk, ledger clean, 407 offline tests green.**
Run `python3 scripts/check_flagships.py <ledger.csv>` after ANY change — it
asserts the 21 validated identifications, that every flagship is tier
**Identified**, and the banned junk classes (incl. O>=12 in Identified).

Pipeline shape: pass 0 (known species, locked, twin-gated) → pass 1 (CHO/CHON
backbone + self-calibration) → pass 2 (GKA series) → pass 3 (evidence-opened
contaminant families) → **iso-envelope completion** → **pre-pass-4 carbon
clamp** → pass 4 (residual iso-pairs/deep series) → pass 5 (known-neutral
completion) → isotope-physics audit → calibrated mass-gate audit →
**iso-envelope completion (2nd sweep)** → **composite detection + de-blending**
→ pass 6 (anchored ladder gap-fill) → tiers.apply_tiers.

## Built this session (v36–v41) — the isotope machinery

- **Isotope-envelope completion** (`isotopes.isotope_pattern` per-element
  convolution + `passes.complete_isotope_envelopes`, before pass 4 + post-audit).
  ~44% of the bright "residual"/Candidate peaks were ISOTOPE SATELLITES (M+2/13C)
  of brighter peaks, not new compounds. Attaches unexplained satellites +
  DISPLACES weak (non-High, weak-score) M0s onto their true parent. Fixed the
  393/395 bug (silanediol Si4+Br M+2 mis-read as a phantom Cl-F-S). iso_child
  276→304; peaks-explained 58.6→60.6%.
- **Composite-peak detection** (`passes.detect_composites`). The M+1 region
  (13C/29Si) is halogen-FREE so it scales only with the assigned compound; if
  observed M0 exceeds the M+1-implied intensity, an unresolved CO-ELUTING
  compound shares the m/z. Reads the co-component's halogen off the even-shift
  residual (M+2/M0, M+4/M+2 ~ Br/BrCl/Br2). The silanediol n>=3 rungs are
  ~30–45% co-eluting BrCl/Br — formula (Si4, proven by +74.0188 rung spacing)
  AND prediction (binomial, Mascope agrees) are BOTH correct; the PEAK is mixed.
- **Composite de-blending** (`passes.split_composites`, user-designed). The
  owner keeps `assigned_fraction` of its measured height; the co-eluting
  compound becomes a SYNTHETIC `<id>.2` sub-peak at the same m/z (synthetic=True,
  host_peak_id->host, carries co_height + co_halogen). Signal conserved:
  silanediol 393 → host eff 10994 + sub 9092 = 20086 measured. stats() uses
  effective height + excludes synthetic from n_peaks. Signal 91.0→90.2% (the
  honest drop = co-component fractions no longer mis-credited).
- 6 adversarial-review findings fixed in the isotope code (81Br mass constant
  was 0.16 mDa off + inconsistent; dead tier-guard; max_shift truncation; flat
  ppm window mislabeling 29Si/13C). See commit c882594.

## What the residual IS (eliminated — do not re-chase)

- **Sulfate / nitrate**: dead (0.06x / 0.0–0.1x decoys; the sample's N lives in
  the small acids + dinitrophenol, see below).
- **The C/H lattice is biogenic SOA** (v30-v32): bright n_Br=2 peaks are
  mono-/sesquiterpene oxidation products as `[M+HBr+Br]-` reagent clusters
  (covalent-Br2 and a Br2 reagent adduct are the SAME ion). 12 di-bromide CHO
  cores assigned (C9–C15 H_xO_4 ladders, e.g. 409=C15H22O3). All CHO-only.
- **The diagonals are MOSTLY NOT new compounds.** Repeatedly characterized
  (workflows + live scoring): the rotating-GKA diagonals are dominated by
  (a) 81Br/13C ISOTOPE SATELLITES of brighter peaks marching as parallel CH2
  ladders (an isotope envelope of a CH2 series IS a CH2 series), and
  (b) fluorinated-contaminant CH2/C2H4O ladders. A non-integer GKA rotation
  makes contaminant ladders + satellites look like SOA — adversarial
  verification (constant-DBE, same-adduct, satellite guard, dedicated isotope
  envelope, live score) is MANDATORY before encoding any diagonal as chemistry.
- **Di-bromide naming campaign on the remaining nBr=2 residual: ZERO new
  names** (workflow wf_94552dc0). All 14 candidates rejected on adversarial
  verification — including 424.99=C15H22O4, whose M+2/M+4 are OWNED by a
  confirmed single-Br fluorinated contaminant (C14H12F8O [M+Br]-), so its +HBr
  pairing only proves a SINGLE-Br adduct. The remaining nBr=2 residual is:
  tribromide/3-Br reagent clusters (194.95/208.96/280.76/282.76/199.85/238.76),
  multi-Br mass-domain-ambiguous (124.92/140.92/192.95/194.94), one
  multiply-charged (239.03), and uncorroborated N2/S mass-fits with FABRICATED
  isotope envelopes (their apparent M+2/M+4 are crowding from adjacent assigned
  di-bromides). The clean di-bromide SOA already got assigned in v41; what
  remains is not nameable from the sum spectrum.
- **Reagent = dibromomethane (CH2Br2)** → Br-/Br2-/Br3- clusters (Br3- DOMINANT
  ~129k cps) + trace HBr. Server has +Br-/+Br2-/+Br3- mechanisms. [M+Br3]- must
  NOT be a blanket scoring channel (timed out batches, lost 40 base M0s incl.
  TFA). OPEN: the [M+HBr+Br]- vs covalent-monobromo [M+Br]- LABEL choice for
  di-bromide cores is the user's call (same ion; 480-cps HBr.Br- argues for
  covalent-monobromo). Left as-is pending decision.

## Next steps, in priority order

1. **Name the composite co-components** (the open de-blending step). The
   `<id>.2` synthetic sub-peaks now sit in the ledger with their m/z + measured
   halogen constraint (the silanediol rungs host ~9k-cps BrCl sub-peaks). Build
   a constrained match on them (halogen pinned, mass fixed) to NAME the
   co-component → this formally allows TWO M0 owners per peak (the data model
   supports it: distinct peak_id, host link, fractional signal). DESIGN CALL the
   user flagged: do we commit the `.2` peak as a second M0?
2. **Add dinitrophenol C6H4N2O5 [M-H]- (183.0047, 808 cps, -0.24 ppm, DBE 6)**
   to the pass-0 known-atmospheric list. A genuine missed nitroaromatic tracer
   (verified credible during the v41 row analysis; the ONE solid new name from
   the diagonal hunting — it is CHON, immune to the di-bromide envelope trap).
   Candidate (tentative): 293.0579 = C15H15ClO4 [M-H]- (respects measured Cl,
   1215 cps, but -2.4 ppm — marginal).
3. **Time-resolved correlation confirmer (THE unlock; user sourcing data).**
   `get_peak_timeseries` hook exists. Co-variation clustering: members of one
   family must correlate; separates inlet contamination (flat) from ambient
   (variable); resolves composites; names whole families from one member. This
   is what would actually crack the multi-halogen tail + confirm the di-bromide
   composites.
4. **Below-assignability certificates.** For each bright has-constraints
   residual peak, run the clamped frame×element enumeration and stamp the result
   into the Unassigned sheet ("searched N frames, zero fits → composite/exotic").
5. **Robustness niceties.** Batch-level re-retry before fail-loud in
   score_candidates; the [M+Br]- vs [M+HBr+Br]- label decision (#OPEN above).

## Standing lessons (encode-don't-remember)

- A di-bromide (or any multi-isotope) name needs its OWN DEDICATED isotope
  envelope — M+2/M+4 at the predicted intensity that isn't already owned by an
  adjacent assigned species. A good ppm + an apparent M+2/M+4 is NOT enough; the
  envelope is routinely fabricated by crowding from neighbors (the v41 campaign:
  all 14 di-bromide candidates failed exactly here).
- The diagonals' "well-aligning rows" are mostly ISOTOPE SATELLITES (an isotope
  envelope of a CH2 series is itself a CH2 ladder) + the multi-halogen lattice.
  Good ppm ≠ real; high-DBE / O-monster / het-ignoring mass-fits are fictions.
- The M+1 region (13C/29Si) is halogen-free → it gives a compound's true
  intensity independent of any coincident halogen co-eluter (the composite test).
- Every evidence GATE needs a complementary RECOVERY path.
- Negative evidence (absent satellite) never overrides independent positive
  evidence (agreeing channel, twin satellite).
- Server scoring is authoritative; never trust hand ion-mass arithmetic.
- Coverage metrics reward fiction; flagships + count-based coverage are honest.
- GKA: trust integer-A(R) rows; verify non-integer rotations; half-integer X is
  a feature (C/H lattice / fixed-heteroatom view).
