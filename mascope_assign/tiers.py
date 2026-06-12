"""Assignment tiers -- the report-level verdict on every M0 claim (ROADMAP 2).

The pipeline commits ONE winning formula per peak, but presenting every commit
as "the identification" overstates what the evidence supports. This module
splits the committed assignments into two report tiers by MECHANICAL rules on
ledger columns (reproducible, no judgment calls at report time):

  Identified -- the formula is unique in the calibrated mass window, or it is
                corroborated by independent evidence (Mascope-confirmed
                isotopologues / attached satellites, the same neutral assigned
                in a second ionization channel, or series-anchor support), and
                nothing about the chemistry contradicts the validated sample
                profile.

  Candidate  -- a plausible formula, honestly ambiguous. Reasons: base
                confidence Low/Suspect; an effective-score near-tie; close
                alternatives in the window without isotope/cross-channel
                discrimination; oxygen count beyond the validated chemistry
                (the O>=12 "lattice monsters" -- mass-fit fantasies sitting on
                the unexplained multi-halogen C/H lattice); or the mixed-BrCl
                family where the isotope pattern pins the halogens but not
                the backbone.

The third tier of the report -- Below assignability -- is the UNEXPLAINED
residual, characterized peak-by-peak in residual.characterize_residual()
(isotope-partner / has-constraints / isolated).

Candidate DENSITY is the confidence currency: how many distinct formulas
live within CLOSE_MARGIN effective score of the winner (winner included).
Density 1 == unique. The stored alternatives list is capped upstream, so a
density equal to 1 + the cap is a lower bound, rendered as ">=N".

Works on OLD ledgers (CSV round-trips without the eff_score/eff_margin/tied
columns): the effective-score margin is recovered from the mechanical
commentary ("nearest competitor ... trails by X"), falling back to the raw
score gap. New ledgers carry the arbitration data directly.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from . import chemistry as C
from . import ledger as L

__version__ = "0.1.0"

TIER_IDENTIFIED = "Identified"
TIER_CANDIDATE = "Candidate"

TIE_MARGIN = 0.05        # arbitrate()'s own near-tie window
CLOSE_MARGIN = 0.10      # alternative within this eff-score of winner = "close"
O_MAX_IDENTIFIED = 11    # validated chemistry tops out at O7 (monoterpene
                         # rungs); O8-11 is plausible HOM-type oxidation; O>=12
                         # only ever appeared as lattice-monster mass fits

_TRAILS_RE = re.compile(r"trails by ([0-9.]+)")


def base_confidence(conf) -> str:
    """'Good (fluorinated)' -> 'Good'."""
    m = re.match(r"\s*([A-Za-z]+)", str(conf) if conf is not None else "")
    return m.group(1) if m else ""


def _alts(cell) -> list[dict]:
    try:
        v = json.loads(cell) if isinstance(cell, str) else (cell or [])
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _truthy(v) -> bool | None:
    """Robust bool for a ledger 'tied' cell that may have round-tripped CSV."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "1"):
        return True
    if s in ("false", "0"):
        return False
    return None


def _winner_raw(row) -> float | None:
    vals = [row.get("ion_score"), row.get("compound_score")]
    vals = [float(v) for v in vals if v is not None and pd.notna(v)]
    return min(vals) if vals else None


def _alt_raw(a: dict) -> float | None:
    for k in ("raw_score", "ion_score", "eff_score"):
        if a.get(k) is not None:
            return float(a[k])
    return None


_ADDUCT_TOKENS = re.compile(r"([+-])([A-Za-z0-9]+)")


def _ion_counts(neutral, adduct) -> dict | None:
    """Element counts of the ION for a (neutral, adduct) reading, or None when
    the adduct string is not parseable. '[M+HBr+Br]-' adds H, 2x Br, etc."""
    if not neutral or not adduct:
        return None
    s = str(adduct).strip()
    if not s.startswith("[M"):
        return None
    cnt = dict(C.parse_formula(str(neutral)))
    for sign, tok in _ADDUCT_TOKENS.findall(s.split("]")[0][2:]):
        for el, n in C.parse_formula(tok).items():
            cnt[el] = cnt.get(el, 0) + (n if sign == "+" else -n)
    return {k: v for k, v in cnt.items() if v}


def _drop_decomposition_aliases(row, alts: list[dict]) -> tuple[list[dict], int]:
    """Remove alternatives that are the SAME ION as the winner under a
    different neutral/adduct split (covalent-vs-cluster decomposition).
    No spectral evidence can ever distinguish those readings -- the adduct
    reading is preferred by policy (2026-06-11) -- so they are NOT competing
    candidates and must not count toward ties or density."""
    ion0 = _ion_counts(row.get("neutral_formula"), row.get("adduct"))
    if ion0 is None:
        return alts, 0
    kept = [a for a in alts
            if _ion_counts(a.get("formula"), a.get("adduct")) != ion0]
    return kept, len(alts) - len(kept)


def _margin_density_tie(row, alts: list[dict], n_aliased: int,
                        n_stored: int) -> tuple[float | None, int, bool, bool]:
    """(margin to best real alternative, candidate density, capped?, tied?).

    margin None == no competing candidate in the search window. Aliases are
    already removed from `alts`; when any were removed, the stored tie flag /
    commentary tie may refer to an alias, so the verdict is recomputed."""
    if not alts:
        return None, 1, False, False
    eff = row.get("eff_score")
    if eff is not None and pd.notna(eff) \
            and any(a.get("eff_score") is not None for a in alts):
        # new ledgers: the arbitration's own effective scores, exact
        margins = [float(eff) - float(a["eff_score"]) for a in alts
                   if a.get("eff_score") is not None]
        margin = min(margins)
        n_close = sum(1 for m in margins if m < CLOSE_MARGIN)
        tied = margin < TIE_MARGIN
    else:
        # old ledger: the mechanical commentary holds the true eff margin --
        # but only trust it when no alias was filtered (it may name the alias)
        m = _TRAILS_RE.search(str(row.get("commentary") or ""))
        wr = _winner_raw(row)
        if m and n_aliased == 0:
            margin = float(m.group(1))
            tied = "(TIE)" in str(row.get("commentary") or "") or margin < TIE_MARGIN
            n_close = 1 if margin < CLOSE_MARGIN else 0
            if wr is not None and len(alts) > 1:
                n_close = max(n_close, sum(
                    1 for a in alts
                    if _alt_raw(a) is not None and wr - _alt_raw(a) < CLOSE_MARGIN))
        elif wr is not None:
            raws = [r for r in (_alt_raw(a) for a in alts) if r is not None]
            if not raws:
                return None, 1, False, False
            margin = wr - max(raws)
            n_close = sum(1 for r in raws if wr - r < CLOSE_MARGIN)
            tied = margin < TIE_MARGIN
        else:
            return None, 1 + len(alts), False, False
    # stored alternatives are capped upstream (arbitrate keeps the top few);
    # if every stored one is close, the true density is a lower bound
    capped = n_stored >= 3 and n_close >= len(alts) and n_close > 0
    return margin, 1 + n_close, capped, tied


def density_text(density: int, capped: bool) -> str:
    return f">={density}" if capped else str(density)


def compute_tiers(ledger: pd.DataFrame) -> pd.DataFrame:
    """One row per M0 peak: [peak_id, tier, tier_reason, candidate_density,
    density_capped]. Pure; does not mutate the ledger."""
    m0 = ledger[ledger["role"] == L.ROLE_M0]
    # corroboration sources
    kids_of = ledger.loc[ledger["role"] == L.ROLE_ISO, "parent_peak_id"].value_counts()
    chan_count = m0.groupby("neutral_formula")["adduct"].nunique()

    rows = []
    for _, r in m0.iterrows():
        formula = str(r.get("neutral_formula") or "")
        counts = C.parse_formula(formula)
        base = base_confidence(r.get("confidence"))
        alts_all = _alts(r.get("alternatives"))
        alts, n_aliased = _drop_decomposition_aliases(r, alts_all)
        margin, density, capped, tied = _margin_density_tie(
            r, alts, n_aliased, len(alts_all))
        if n_aliased == 0:
            # the arbitration's stored verdict is authoritative when no alias
            # polluted the runner-up slot
            stored = _truthy(r.get("tied"))
            if stored is not None:
                tied = stored
            elif "(TIE)" in str(r.get("commentary") or ""):
                tied = True
        iso_ev = (kids_of.get(r["peak_id"], 0) > 0) or bool(_alts(r.get("isotopologues")))
        cross_channel = int(chan_count.get(formula, 0)) >= 2
        has_anchor = pd.notna(r.get("anchor_peak_id")) or pd.notna(r.get("series_unit"))
        corroborated = iso_ev or cross_channel or has_anchor

        method = str(r.get("method") or "")
        tier, reason = TIER_IDENTIFIED, ""
        if method.startswith("known:"):
            reason = ("known species (pass-0 locked list, mass + own-twin "
                      "self-consistency gated)")
        elif base in ("Low", "Suspect"):
            tier = TIER_CANDIDATE
            reason = (f"{base} confidence: score/mass evidence below the "
                      "identification bar")
        elif counts.get("O", 0) > O_MAX_IDENTIFIED:
            tier = TIER_CANDIDATE
            reason = (f"O{counts['O']} exceeds validated chemistry for this "
                      "matrix (flagships top out at O7); mass sits in the "
                      "unexplained C/H-lattice region -- likely a lattice "
                      "family member wearing a CHO(N) mass fit")
        elif counts.get("Br", 0) >= 1 and counts.get("Cl", 0) >= 1:
            tier = TIER_CANDIDATE
            reason = ("mixed Br/Cl halogenation: the isotope envelope pins the "
                      "halogen count but the backbone candidates stay ambiguous")
        elif tied and not (cross_channel or has_anchor):
            # a spectral eff-score tie cannot be broken by isotopes (they are
            # already in the score) -- only extra-spectral corroboration
            # (second channel, series anchor) rescues a tied winner
            alt0 = alts[0].get("formula", "?") if alts else "?"
            tier = TIER_CANDIDATE
            reason = (f"near-tie: best alternative ({alt0}) within "
                      f"{TIE_MARGIN} effective score")
        elif density > 1 and not corroborated:
            tier = TIER_CANDIDATE
            reason = (f"{density - 1} alternative(s) within {CLOSE_MARGIN} "
                      "effective score and no isotope / cross-channel / "
                      "series corroboration to discriminate")
        else:
            parts = []
            if density == 1:
                parts.append("unique formula in the calibrated window"
                             + (f" ({n_aliased} same-ion decomposition "
                                "reading(s) excluded)" if n_aliased else ""))
            else:
                parts.append(f"best of {density_text(density, capped)} candidates "
                             f"(margin {margin:.2f})" if margin is not None else
                             f"best of {density_text(density, capped)} candidates")
            if iso_ev:
                parts.append("isotopologue-confirmed")
            if cross_channel:
                parts.append("seen in a second ionization channel")
            if has_anchor:
                parts.append("series-anchor support")
            reason = "; ".join(parts)
        rows.append({"peak_id": r["peak_id"], "tier": tier, "tier_reason": reason,
                     "candidate_density": density, "density_capped": capped})
    return pd.DataFrame(rows, columns=["peak_id", "tier", "tier_reason",
                                       "candidate_density", "density_capped"])


def apply_tiers(ledger: pd.DataFrame) -> pd.DataFrame:
    """Stamp tier / tier_reason / candidate_density onto the M0 rows of the
    ledger (in place; returns the ledger). Non-M0 rows keep NA."""
    for col in ("tier", "tier_reason", "candidate_density"):
        if col not in ledger.columns:
            ledger[col] = pd.Series(pd.NA, index=ledger.index, dtype="object")
        elif ledger[col].dtype != object:
            # candidate_density holds '>=N' strings; a float column (e.g. an
            # all-NaN CSV round-trip) must widen before the stamp
            ledger[col] = ledger[col].astype("object")
    t = compute_tiers(ledger)
    if not len(t):
        return ledger
    idx = ledger.index[ledger["peak_id"].isin(t["peak_id"])]
    by_pid = t.set_index("peak_id")
    for i in idx:
        pid = ledger.at[i, "peak_id"]
        ledger.at[i, "tier"] = by_pid.at[pid, "tier"]
        ledger.at[i, "tier_reason"] = by_pid.at[pid, "tier_reason"]
        ledger.at[i, "candidate_density"] = density_text(
            int(by_pid.at[pid, "candidate_density"]),
            bool(by_pid.at[pid, "density_capped"]))
    return ledger
