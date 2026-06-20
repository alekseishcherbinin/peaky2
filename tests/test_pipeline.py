"""Offline tests for pipeline.py run-versioning helpers (deterministic via a
fixed datetime). Run: python3 tests/test_pipeline.py"""
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mascope_assign import pipeline as PL  # noqa: E402

PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ok  {name}")
    else: FAIL += 1; print(f"FAIL  {name}  {detail}")


WHEN = datetime(2026, 6, 20, 14, 35, 12)

check("slugify: spaces/punct -> single dashes, trimmed",
      PL.slugify("Orange peeling (Ur+ CIMS)") == "Orange-peeling-Ur-CIMS",
      PL.slugify("Orange peeling (Ur+ CIMS)"))
check("slugify: empty -> 'run'", PL.slugify("  ") == "run")

folder, human = PL.run_stamp(WHEN)
check("run_stamp: folder stamp has date+time to the second", folder == "2026-06-20_143512", folder)
check("run_stamp: human stamp is date + HH:MM", human == "2026-06-20 14:35", human)

rid = PL.run_id("Orange peeling (Ur+ CIMS)", WHEN)
check("run_id: slug + date + time", rid == "Orange-peeling-Ur-CIMS_2026-06-20_143512", rid)

with tempfile.TemporaryDirectory() as d:
    rd = PL.make_run_dir(d, "Orange peeling (Br- CIMS)", WHEN)
    check("make_run_dir: creates a fresh per-run folder", os.path.isdir(rd), rd)
    check("make_run_dir: folder basename == run_id (id locates the folder)",
          os.path.basename(rd) == PL.run_id("Orange peeling (Br- CIMS)", WHEN),
          os.path.basename(rd))
    check("make_run_dir: name carries the batch, the date AND the time",
          "Orange-peeling-Br-CIMS" in os.path.basename(rd)
          and "2026-06-20" in os.path.basename(rd) and "143512" in os.path.basename(rd))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
