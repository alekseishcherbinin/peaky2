"""Offline tests for reagents.py. Run: python3 tests/test_reagents.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mascope_assign import reagents as RG  # noqa: E402
from mascope_assign import ledger as L  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}  {detail}")


def near(lib, mz, ppm=10):
    return [lbl for lbl, m in lib if abs(m - mz) / mz * 1e6 <= ppm]


# --- library contains Br-, [Br3]- and isotopologues at the right masses ---
lib = RG.build_library("Br")
check("Br- present ~78.9189", bool(near(lib, 78.9189)), near(lib, 78.9189))
# tribromide [Br3]- monoisotopic 3*78.9183 + e = 236.7555
check("[Br3]- present ~236.7555", bool(near(lib, 236.7555)), near(lib, 236.7555))
# isotopologue 79Br2 81Br at ~238.7535
check("[Br3]- 79,79,81 isotopologue ~238.7535", bool(near(lib, 238.7535)), near(lib, 238.7535))
# Br . H2O cluster ~ 78.9189 + 18.0106 = 96.929 (HNO3/HNO2 were removed from
# the cluster library 2026-06-12 -- they are ambient analytes assigned in pass 0)
check("[Br+H2O]- present ~96.929", bool(near(lib, 96.929)), near(lib, 96.929))
check("HNO3 NOT in reagent library (now an analyte)", not near(lib, 141.914))
# di-bromide radical anion Br2-. = 2*78.9183 + e = 157.8372 (user registered it
# on the server 2026-06-12); the labeler must catch bare even-n clusters too
check("[Br2]-. present ~157.8372", bool(near(lib, 157.8372)), near(lib, 157.8372))
# ambient ORGANIC ACIDS were removed from the cluster library: [Br+HCOOH]- =
# [CH2O2+Br]- = the analyte channel (formic acid's 124.92/126.92 giants), so it
# must NOT be a reagent label anymore
check("[Br+HCOOH]- (124.924) NOT in reagent library (it is the [M+Br]- analyte)",
      not near(lib, 124.924), near(lib, 124.924))
check("[Br+pinic]- (267.006) NOT in reagent library", not near(lib, 267.006))
# HBr cluster on the di-bromide core stays reagent (pure halogen, no analyte):
# [Br2+HBr]- = 157.8372 + 79.926 = 237.763
check("[Br+HBr]- (HBr2- ~160.843) still reagent", bool(near(lib, 160.843)))

# --- reagent_for_adducts ---
check("Br reagent from [M+Br]-", RG.reagent_for_adducts(["[M-H]-", "[M+Br]-"]) == "Br")
check("I reagent from [M+I]-", RG.reagent_for_adducts(["[M+I]-"]) == "I")
check("None when no halide reagent", RG.reagent_for_adducts(["[M-H]-", "[M+NO3]-"]) is None)

# --- labeler marks the bright Br3 cluster peaks ---
peaks = pd.DataFrame({
    "peak_id": ["b1", "b3", "b3b", "org"],
    "mz": [78.9189, 236.7555, 238.7535, 257.0181],
    "height": [2e5, 1e5, 9e4, 8e4],
})
led = L.new_ledger(peaks)
n = RG.label_reagents(led, "Br", ppm=15)
check("labels >=3 reagent peaks", n >= 3, n)
check("Br3 peak labeled reagent",
      L.role_of(led, "b3") == L.ROLE_REAGENT, L.role_of(led, "b3"))
check("organic peak NOT labeled reagent",
      L.role_of(led, "org") == L.ROLE_UNEXPLAINED, L.role_of(led, "org"))
check("reagent commentary written",
      "reagent ion" in str(led.loc[led.peak_id == "b3", "commentary"].iloc[0]))

# --- does not touch assigned peaks ---
led2 = L.new_ledger(peaks)
L.commit_assignment(led2, "b3", neutral_formula="C5H8O2", adduct="[M-H]-",
                    ion_score=0.9, pass_no=1, method="x", confidence="High",
                    commentary="real assignment")
RG.label_reagents(led2, "Br", ppm=15)
check("assigned peak not overwritten by reagent labeler",
      L.role_of(led2, "b3") == L.ROLE_M0)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
