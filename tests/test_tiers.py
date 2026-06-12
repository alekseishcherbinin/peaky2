"""Offline tests for tiers.py. Run: python3 tests/test_tiers.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mascope_assign import ledger as L  # noqa: E402
from mascope_assign import tiers as T  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}  {detail}")


peaks = pd.DataFrame({
    "peak_id": list("ABCDEFGHIJKL"),
    "mz": [200.1, 201.1, 191.0, 510.99, 392.89, 250.0, 251.0, 252.0,
           300.0, 301.0, 555.5, 556.5],
    "height": [1e5, 1e4, 8e4, 1.1e4, 9e2, 5e4, 4e4, 3e4, 2e4, 1e4, 6e3, 5e3]})
led = L.new_ledger(peaks)

# A: High, isotopologue-confirmed, clear margin -> Identified
L.commit_assignment(led, "A", neutral_formula="C10H16O4", adduct="[M-H]-",
                    ion_formula="C10H15O4-", ion_score=0.97, compound_score=0.96,
                    eff_score=0.95, eff_margin=0.20, tied=False,
                    ppm_error=-0.3, pass_no=1, method="cheminfo+grid",
                    confidence="High", commentary="Pass 1",
                    alternatives=[{"formula": "C9H13NO5", "ion_score": 0.80,
                                   "raw_score": 0.80, "eff_score": 0.75, "ppm": 0.8}],
                    isotopologues=[{"label": "13C", "score": 0.93, "peak_id": "B"}])
L.attach_isotopologue(led, "B", "A", iso_label="13C", iso_match_score=0.93)

# C: Good, NO corroboration, close alternative -> Candidate (density rule)
L.commit_assignment(led, "C", neutral_formula="C7H12O4", adduct="[M-H]-",
                    ion_formula="C7H11O4-", ion_score=0.83, compound_score=0.83,
                    eff_score=0.82, eff_margin=0.07, tied=False,
                    ppm_error=0.5, pass_no=1, method="cheminfo+grid",
                    confidence="Good", commentary="Pass 1",
                    alternatives=[{"formula": "C3H8N2O6", "ion_score": 0.81,
                                   "raw_score": 0.81, "eff_score": 0.75, "ppm": 0.9}])

# D: 'High' O>=12 lattice monster -> Candidate
L.commit_assignment(led, "D", neutral_formula="C14H12N2O19", adduct="[M-H]-",
                    ion_formula="C14H11N2O19-", ion_score=0.92, compound_score=0.92,
                    eff_score=0.90, eff_margin=0.3, tied=False,
                    ppm_error=0.4, pass_no=1, method="cheminfo+grid",
                    confidence="High", commentary="Pass 1",
                    isotopologues=[{"label": "13C", "score": 0.9, "peak_id": "E"}])

# E: mixed Br/Cl neutral -> Candidate (even at Good confidence)
L.commit_assignment(led, "E", neutral_formula="C9H4BrClO2", adduct="[M-H]-",
                    ion_formula="C9H3BrClO2-", ion_score=0.86, compound_score=0.86,
                    ppm_error=-0.2, pass_no=4, method="residual:iso-pair",
                    confidence="Good (iso-pair)", commentary="Pass 4 (iso-pair): BrCl doublet")

# F: known species (pass-0) -> Identified regardless of alternatives
L.commit_assignment(led, "F", neutral_formula="C4H14O3Si2", adduct="[M+Br]-",
                    ion_formula="C4H14O3Si2.Br-", ion_score=0.95, compound_score=0.94,
                    ppm_error=0.1, pass_no=0, method="known:contaminant:silanediol",
                    confidence="Good (contaminant)", commentary="Pass 0 (known contaminant)")

# G: Low confidence -> Candidate
L.commit_assignment(led, "G", neutral_formula="C5H8O3", adduct="[M+Br]-",
                    ion_formula="C5H8O3.Br-", ion_score=0.62, compound_score=0.62,
                    ppm_error=1.2, pass_no=4, method="residual:series",
                    confidence="Low (deep-series)", commentary="Pass 4")

# H: Good, near-tie via stored arbitration columns -> Candidate
L.commit_assignment(led, "H", neutral_formula="C6H10O4", adduct="[M-H]-",
                    ion_formula="C6H9O4-", ion_score=0.85, compound_score=0.85,
                    eff_score=0.84, eff_margin=0.02, tied=True,
                    ppm_error=0.3, pass_no=1, method="cheminfo+grid",
                    confidence="Good", commentary="Pass 1",
                    alternatives=[{"formula": "C2H6N2O6", "ion_score": 0.84,
                                   "raw_score": 0.84, "eff_score": 0.82, "ppm": 0.4}],
                    isotopologues=[{"label": "13C", "score": 0.8, "peak_id": "I"}])

# I: OLD-LEDGER fallback -- no eff columns, tie only visible in commentary
L.commit_assignment(led, "I", neutral_formula="C8H14O5", adduct="[M-H]-",
                    ion_formula="C8H13O5-", ion_score=0.88, compound_score=0.88,
                    ppm_error=0.2, pass_no=1, method="cheminfo+grid",
                    confidence="Good",
                    commentary="Pass 1. Nearest competitor C4H10N2O7 trails by 0.03 (TIE)",
                    alternatives=[{"formula": "C4H10N2O7", "ion_score": 0.87,
                                   "raw_score": 0.87, "ppm": 0.5}])

# J: Good, cross-channel corroboration (same neutral as A, other adduct),
# close alternative present -> Identified via corroboration
L.commit_assignment(led, "J", neutral_formula="C10H16O4", adduct="[M+Br]-",
                    ion_formula="C10H16O4.Br-", ion_score=0.84, compound_score=0.84,
                    eff_score=0.80, eff_margin=0.08, tied=False,
                    ppm_error=0.6, pass_no=5, method="completion:known-neutral",
                    confidence="Good (completion)", commentary="Pass 5",
                    alternatives=[{"formula": "C6H12N2O6", "ion_score": 0.82,
                                   "raw_score": 0.82, "eff_score": 0.74, "ppm": 0.7}])

t = T.compute_tiers(led).set_index("peak_id")

check("A High + iso + margin -> Identified", t.at["A", "tier"] == "Identified", t.loc["A"].to_dict())
check("A reason mentions isotopologue", "isotopologue" in t.at["A", "tier_reason"])
check("C close alt, no corroboration -> Candidate", t.at["C", "tier"] == "Candidate")
check("D O19 monster -> Candidate despite High", t.at["D", "tier"] == "Candidate")
check("D reason mentions lattice", "lattice" in t.at["D", "tier_reason"])
check("E mixed BrCl -> Candidate", t.at["E", "tier"] == "Candidate")
check("F known species -> Identified", t.at["F", "tier"] == "Identified")
check("G Low -> Candidate", t.at["G", "tier"] == "Candidate")
check("H stored near-tie -> Candidate", t.at["H", "tier"] == "Candidate")
check("H reason is the tie", "near-tie" in t.at["H", "tier_reason"], t.at["H", "tier_reason"])
check("I commentary-tie fallback -> Candidate", t.at["I", "tier"] == "Candidate")
check("J cross-channel corroboration -> Identified", t.at["J", "tier"] == "Identified",
      t.loc["J"].to_dict())
check("J reason mentions second channel", "second ionization channel" in t.at["J", "tier_reason"])
check("density: A counts winner only when alt is far",
      int(t.at["A", "candidate_density"]) == 1, t.at["A", "candidate_density"])
check("density: H counts the close alt",
      int(t.at["H", "candidate_density"]) == 2, t.at["H", "candidate_density"])

# CSV round-trip: tied becomes the string 'True'/'False'; tiers must agree
import io  # noqa: E402
rt = pd.read_csv(io.StringIO(led.to_csv(index=False)))
t2 = T.compute_tiers(rt).set_index("peak_id")
check("CSV round-trip preserves every tier",
      (t2["tier"] == t["tier"]).all(),
      t2.loc[t2["tier"] != t["tier"], "tier"].to_dict())

# apply_tiers stamps the ledger
T.apply_tiers(led)
m0 = led[led["role"] == "M0"]
check("apply_tiers fills every M0 row", m0["tier"].notna().all())
check("apply_tiers leaves iso/unexplained NA",
      led.loc[led["role"] != "M0", "tier"].isna().all())
check("candidate_density rendered as text", isinstance(m0["candidate_density"].iloc[0], str))

# base_confidence parsing
check("base_confidence strips suffix", T.base_confidence("Good (fluorinated)") == "Good")
check("base_confidence handles NA", T.base_confidence(None) == "")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
