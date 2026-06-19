"""Pipeline spine — `run(batch, reagent)` instead of a copy-pasted script per
dataset. Resolves a reagent profile, loads the batch (SDK or a cached parquet),
and dispatches the requested stages, all parameterised by the profile.

This is the thin orchestrator the rest of agent-peaky hangs off. Stage functions
live in their own modules and are called with profile params — nothing reagent-
or batch-specific is hardcoded here.

Stages: 'matrix' (TS intensity matrix) is wired; 'assign' / 'cluster' / 'validate'
are folded in as their scratch logic is consolidated into the package.
"""
from __future__ import annotations

import os
import pandas as pd

from . import io_mascope as IO
from . import profiles as P
from . import timeseries as TS

__version__ = "0.1.0"

STAGES = ("matrix", "assign", "cluster", "validate")


def load(*, batch: str | None = None, dataset: str | None = None,
         peaks: "str | pd.DataFrame | None" = None, save_path: str | None = None
         ) -> pd.DataFrame:
    """Get the batch peak time-series — from a parquet/DataFrame if given (offline,
    cached), else fetched from Mascope via the SDK."""
    if peaks is not None:
        return pd.read_parquet(os.path.expanduser(peaks)) if isinstance(peaks, str) else peaks
    if not (batch and dataset):
        raise ValueError("need peaks=, or both batch= and dataset=")
    return IO.fetch_batch_peaks(IO.connect(), dataset, batch, save_path=save_path)


def run(*, batch: str | None = None, dataset: str | None = None,
        peaks: "str | pd.DataFrame | None" = None, reagent: str = "auto",
        stages: tuple = ("matrix",), out_dir: str | None = None) -> dict:
    """Run the pipeline on one batch.

    Returns a dict with at least {profile, peaks, n_samples} plus per-stage outputs.
    Pass reagent by name ('Br'/'Ur') or 'auto' to detect from the data.
    """
    pk = load(batch=batch, dataset=dataset, peaks=peaks)
    prof = P.resolve(reagent, pk)
    n_samples = pk["sample_item_name"].nunique() if "sample_item_name" in pk.columns else None
    out: dict = {"profile": prof, "peaks": pk, "n_samples": n_samples,
                 "stages": tuple(stages)}

    if "matrix" in stages:
        mat, bin_mz = TS.build_matrix(pk)
        out["matrix"] = mat
        out["bin_mz"] = bin_mz

    # 'assign' / 'cluster' / 'validate' are added as the scratch modules
    # (cluster_*, isotope_validate) are consolidated into the package against
    # isotopes.py. Flag clearly until then rather than silently no-op.
    todo = [s for s in stages if s in ("assign", "cluster", "validate")]
    if todo:
        out["pending_stages"] = todo
        if n_samples and n_samples < 12 and "cluster" in todo:
            out["cluster_warning"] = (f"{n_samples} samples < 12: temporal clustering "
                                      "unreliable; isotope/coverage layer preferred")

    if out_dir:
        os.makedirs(os.path.expanduser(out_dir), exist_ok=True)
    return out
