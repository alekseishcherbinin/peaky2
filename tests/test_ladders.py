"""Offline tests for ladders.py (anchored gap-fill). Run: python3 tests/test_ladders.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mascope_assign import chemistry as C  # noqa: E402
from mascope_assign import ladders as LAD  # noqa: E402
from mascope_assign import ledger as L  # noqa: E402
from mascope_assign import passes as P  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}  {detail}")


# ---- unit helpers ----
check("_apply +O adds an oxygen", LAD._apply({"C": 15, "H": 24, "O": 2}, {"O": 1}, 1)
      == {"C": 15, "H": 24, "O": 3})
check("_apply +C2H4 x2", LAD._apply({"C": 9, "H": 12, "O": 4}, {"C": 2, "H": 4}, 2)
      == {"C": 13, "H": 20, "O": 4})
check("_apply refuses negative", LAD._apply({"C": 1, "H": 2}, {"C": -1, "H": -2}, 2) is None)
check("_scoreable HBr+Br -> covalent [M-H]-",
      LAD._scoreable("C15H22O4", "[M+HBr+Br]-") == ("C15H24Br2O4", "[M-H]-"))
check("_scoreable [M+Br]- stays native",
      LAD._scoreable("C15H24O3", "[M+Br]-") == ("C15H24O3", "[M+Br]-"))

# ---- isotope-satellite guard ----
import numpy as np  # noqa: E402
mzs = np.array([300.0000, 301.99795, 301.0034])  # base, 81Br line, 13C line
hs = np.array([1.0e4, 9.0e3, 2.0e2])
check("guard flags an 81Br satellite (ratio ~0.9)",
      LAD._is_iso_satellite(mzs, hs, 301.99795, 9.0e3))
check("guard flags a 13C satellite (ratio ~0.02)",
      LAD._is_iso_satellite(mzs, hs, 301.0034, 2.0e2))
check("guard passes a genuine isolated peak",
      not LAD._is_iso_satellite(mzs, hs, 305.0000, 5.0e3))

# ---- end-to-end with a mock scorer: the worked C15H22O3 -> O4 oxidation gap ----
cfg = P.PassConfig(height_cutoff=100.0)
cfg.cal_mu, cfg.cal_sigma = 0.0, 0.5   # calibrated so confidence labels work
prof = type("Prof", (), {"label": "ambient-air"})()
anchor_mz = C.ion_mz("C15H22O3", "[M+HBr+Br]-")    # 409.0019
gap_mz = C.ion_mz("C15H22O4", "[M+HBr+Br]-")        # 424.9969 (the +O rung)
far = 600.0
peaks = pd.DataFrame({"peak_id": ["anc", "gap", "far"],
                      "mz": [anchor_mz, gap_mz, far],
                      "height": [4719.0, 1184.0, 500.0]})
led = L.new_ledger(peaks)
L.commit_assignment(led, "anc", neutral_formula="C15H22O3", adduct="[M+HBr+Br]-",
                    ion_formula="C15H23Br2O3-", ion_score=0.93, compound_score=0.93,
                    ppm_error=-1.0, pass_no=4, method="residual:iso-pair",
                    confidence="Good (iso-pair)", commentary="anchor")

# mock score_fn: returns a strong base row for the covalent-equiv of C15H22O4
def mock_score(client, sample_id, formulas, mechanism_ids=None):
    cov = "C15H24Br2O4"   # = C15H22O4 [M+HBr+Br]- covalent equiv
    if cov not in formulas:
        return pd.DataFrame()
    return pd.DataFrame([{
        "is_base": True, "sample_peak_id": "gap", "sample_peak_mz": gap_mz,
        "compound_formula": cov, "ion_formula": "C15H23Br2O4-",
        "ion_score": 0.69, "compound_score": 0.69, "ppm_error": -0.6,
        "iso_label": "M0", "iso_score": None}])

out = LAD.run_ladder_gapfill(None, "S", led, prof, cfg, ["[M+Br]-", "[M+HBr+Br]-"],
                             score_fn=mock_score, log=lambda *a: None)
check("gap-fill commits the +O rung", out["committed"] == 1, out)
check("gap peak now M0", L.role_of(led, "gap") == "M0")
gr = led[led.peak_id == "gap"].iloc[0]
check("gap relabelled to bromine-free C15H22O4 [M+HBr+Br]-",
      gr["neutral_formula"] == "C15H22O4" and gr["adduct"] == "[M+HBr+Br]-",
      (gr["neutral_formula"], gr["adduct"]))
check("gap method is ladder:gapfill", gr["method"] == "ladder:gapfill")
check("gap commentary names the +O step from the anchor",
      "+1x+O" in str(gr["commentary"]) and "C15H22O3" in str(gr["commentary"]),
      gr["commentary"])
check("gap is Candidate-grade (not High)", not str(gr["confidence"]).startswith("High"))
check("far peak untouched", L.role_of(led, "far") == "unexplained")
check("ledger validates", L.validate(led) == [], L.validate(led))

# strong competing M0 is not overwritten
led2 = L.new_ledger(peaks)
L.commit_assignment(led2, "anc", neutral_formula="C15H22O3", adduct="[M+HBr+Br]-",
                    ion_formula="C15H23Br2O3-", ion_score=0.93, compound_score=0.93,
                    ppm_error=-1.0, pass_no=4, method="x", confidence="Good", commentary="a")
L.commit_assignment(led2, "gap", neutral_formula="C9H4F12", adduct="[M-H]-",
                    ion_score=0.97, compound_score=0.97, ppm_error=0.1, pass_no=1,
                    method="x", confidence="High", commentary="strong fluorinated M0")
out2 = LAD.run_ladder_gapfill(None, "S", led2, prof, cfg, ["[M+Br]-", "[M+HBr+Br]-"],
                              score_fn=mock_score, log=lambda *a: None)
check("strong competing M0 not overwritten",
      led2[led2.peak_id == "gap"].iloc[0]["neutral_formula"] == "C9H4F12"
      and out2["rejected_overwrite"] >= 1, out2)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
