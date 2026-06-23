"""Determinism regression — the run's reproducibility contract.

A run is a deterministic function of its inputs + its `when`. The driver
(`pipeline.stamp_source_date_epoch`) exports `when` as SOURCE_DATE_EPOCH; from
there:
  * matplotlib stamps it (not now()) into PNG/PDF metadata, and
  * the xlsx writer reads it via `cluster._resolve_when`,
so every figure / PDF / workbook is byte-identical on a re-run at the same `when`,
and a different `when` changes the bytes (the stamp tracks the run, like the
Report ID). This test locks that contract for ALL THREE artifact types and for
the actual `stamp_source_date_epoch` helper the pipeline calls.

Run: python3 tests/test_determinism.py
"""
import hashlib
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from peaky import cluster as CL  # noqa: E402
from peaky.pipeline import stamp_source_date_epoch  # noqa: E402

PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ok  {name}")
    else: FAIL += 1; print(f"FAIL  {name}  {detail}")


def render(path, fmt):
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.plot([0, 1, 2], [2, 1, 3]); ax.set_title("determinism")
    fig.savefig(path, format=fmt); plt.close(fig)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# rows shape for write_cluster_workbook: [(cid, members, rbar, shape, peak_hr), ...]
_ROWS = [("c1", ["m1", "m2"], 0.91, "rise", 3.5),
         ("c2", ["m3"], 0.80, "fall", 9.0)]
_META = {"m1": {"neutral_formula": "C4H6O4", "tier": "Identified"},
         "m2": {"neutral_formula": "C5H8O4", "tier": "Candidate"},
         "m3": {"neutral_formula": "C6H10O5", "tier": "Identified"}}


def xlsx(path):
    CL.write_cluster_workbook(_ROWS, path, meta=_META, member_cols=["neutral_formula", "tier"])


with tempfile.TemporaryDirectory() as d:
    # ---- 1. low-level: matplotlib honours a fixed SOURCE_DATE_EPOCH ----
    os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
    a, b = os.path.join(d, "a.pdf"), os.path.join(d, "b.pdf")
    render(a, "pdf"); render(b, "pdf")
    check("PDF byte-identical at a fixed SOURCE_DATE_EPOCH",
          sha(a) == sha(b), f"{sha(a)[:10]} vs {sha(b)[:10]}")

    os.environ["SOURCE_DATE_EPOCH"] = "1800000000"
    c = os.path.join(d, "c.pdf"); render(c, "pdf")
    check("PDF bytes change when SOURCE_DATE_EPOCH changes (stamp tracks the run)",
          sha(c) != sha(a), "matplotlib not honouring SOURCE_DATE_EPOCH")

    os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
    e, f = os.path.join(d, "e.png"), os.path.join(d, "f.png")
    render(e, "png"); render(f, "png")
    check("PNG byte-identical at a fixed SOURCE_DATE_EPOCH",
          sha(e) == sha(f), f"{sha(e)[:10]} vs {sha(f)[:10]}")

    # ---- 2. the actual helper the pipeline calls ----
    w1 = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)
    w2 = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    os.environ.pop("SOURCE_DATE_EPOCH", None)
    got = stamp_source_date_epoch(w1)
    check("stamp_source_date_epoch sets SOURCE_DATE_EPOCH to the run epoch",
          os.environ.get("SOURCE_DATE_EPOCH") == got == str(int(w1.timestamp())), got)
    # naive datetime is treated as UTC (no crash, no local-tz drift)
    naive = stamp_source_date_epoch(datetime(2026, 6, 23, 12, 0))
    check("stamp_source_date_epoch treats a naive datetime as UTC",
          naive == str(int(w1.timestamp())), naive)

    # ---- 3. end-to-end: all THREE artifact types stable across a re-run at the
    #         same `when`, and changed at a different `when` — driven only by the
    #         helper (no manual env juggling), exactly as the pipeline does it. ----
    def artifacts(tag):
        stamp_source_date_epoch(w1)
        pdf = os.path.join(d, f"{tag}.pdf"); render(pdf, "pdf")
        png = os.path.join(d, f"{tag}.png"); render(png, "png")
        xl = os.path.join(d, f"{tag}.xlsx"); xlsx(xl)
        return sha(pdf), sha(png), sha(xl)

    run1 = artifacts("run1")
    run2 = artifacts("run2")               # same when -> identical
    check("re-run at the same when -> identical PDF", run1[0] == run2[0])
    check("re-run at the same when -> identical PNG", run1[1] == run2[1])
    check("re-run at the same when -> identical xlsx (write_cluster_workbook)",
          run1[2] == run2[2], f"{run1[2][:10]} vs {run2[2][:10]}")

    stamp_source_date_epoch(w2)            # different when -> different bytes
    pdf2 = os.path.join(d, "later.pdf"); render(pdf2, "pdf")
    xl2 = os.path.join(d, "later.xlsx"); xlsx(xl2)
    check("a later when -> different PDF bytes", sha(pdf2) != run1[0])
    check("a later when -> different xlsx bytes", sha(xl2) != run1[2])


def test_all():
    assert FAIL == 0, f"{FAIL} checks failed"


if __name__ == "__main__":
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
