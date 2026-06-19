"""Standard PDF report for a representative-batch assignment run.

Assembles the assignment findings into one PDF per batch: cover + headline,
coverage stats (assigned vs unassigned, by count AND signal), composition / full
Van Krevelen, analyte families, correlated-cluster TS figures, and methods.

ITERABLE BY DESIGN: the report is an ordered list of SECTIONS, each a function
`section(ctx, pdf)` that draws one or more pages. To change the report, edit /
reorder / add a section function and list it in SECTIONS — nothing else couples.
`ctx` is a dict loaded once by `load_context()` from the run's on-disk artifacts
(merged_ledger.csv, per_file/*, the figures, *_summary.json), so a section just
reads what it needs and degrades gracefully when an artifact is missing.

Pure matplotlib (PdfPages) — no new dependencies, no web stack. Build with
`build(out_dir, tag=..., label=..., ts_path=...)`.
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

__version__ = "0.1.0"

A4 = (8.27, 11.69)                       # portrait inches
INK = "#222222"
GREY = "#777777"


# ---------------------------------------------------------------------------
# context: load everything the report needs, once
# ---------------------------------------------------------------------------
def _skill_version() -> str:
    """Identify the skill build: assign version + git short SHA of this repo."""
    import subprocess
    d = os.path.dirname(os.path.abspath(__file__))
    sha = "?"
    try:
        sha = subprocess.check_output(["git", "-C", d, "rev-parse", "--short", "HEAD"],
                                      text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        pass
    try:
        from . import assign
        av = assign.__version__
    except Exception:
        av = "?"
    return f"mascope_assign (assign v{av}) · git {sha}"


def load_context(out_dir: str, *, tag: str, label: str, ts_path: str | None = None,
                 generated: str = "", batch_name: str | None = None) -> dict:
    from . import analyte_viz as V
    from . import chemistry as C
    out_dir = os.path.expanduser(out_dir)
    ctx: dict = {"out_dir": out_dir, "tag": tag, "label": label, "fig": {},
                 "generated": generated, "version": _skill_version(),
                 "batch_name": batch_name}

    merged = pd.read_csv(f"{out_dir}/merged_ledger.csv")
    ctx["merged"] = merged
    ctx["n_m0"] = len(merged)
    ctx["tiers"] = merged["tier"].value_counts().to_dict()
    u = merged.drop_duplicates("neutral_formula").copy()
    ctx["n_neutrals"] = len(u)
    # composition by CHO/CHON/CHOS backbone (Si/F/halogen folded in)
    ctx["composition"] = u["neutral_formula"].map(V.backbone_class).value_counts().to_dict()
    # heteroatom side-counts (additions to the backbone)
    cnt = u["neutral_formula"].map(lambda f: C.parse_formula(str(f)))
    ctx["hetero"] = {
        "Si-bearing": int(cnt.map(lambda c: c.get("Si", 0) > 0).sum()),
        "F-bearing": int(cnt.map(lambda c: c.get("F", 0) > 0).sum()),
        "Cl/Br in neutral": int(cnt.map(lambda c: c.get("Cl", 0) + c.get("Br", 0) > 0).sum()),
    }
    # match score per tier + adduct-channel breakdown (assignment-quality page)
    if "ion_score" in merged.columns:
        gs = merged.groupby("tier")["ion_score"].mean()
        ctx["score_by_tier"] = {t: float(gs[t]) for t in gs.index}
    ctx["adduct_cat"] = (merged["adduct"].map(_adduct_cat).value_counts().to_dict())
    # the representative sample NAMES (timestamps), not just ids
    ss = f"{out_dir}/selected_samples.csv"
    if os.path.exists(ss):
        s = pd.read_csv(ss)
        name = s["sample_item_name"] if "sample_item_name" in s.columns else s["sample_item_id"]
        ctx["samples"] = list(zip(name.astype(str), s.get("role", pd.Series([""] * len(s))).astype(str)))

    # per-file pooled role breakdown (count + signal) + the explained m/z set
    rows = []
    for f in sorted(glob.glob(f"{out_dir}/per_file/*_ledger.csv")):
        d = pd.read_csv(f)
        d["h"] = pd.to_numeric(d.get("height"), errors="coerce").fillna(0)
        rows.append(d)
    ctx["n_files"] = len(rows)
    if rows:
        a = pd.concat(rows, ignore_index=True)
        ctx["role_count"] = a["role"].value_counts().to_dict()
        ctx["role_signal"] = {k: float(v) for k, v in a.groupby("role")["h"].sum().items()}
        ctx["expl_mz"] = np.sort(a.loc[a["role"].astype(str) != "unexplained",
                                       "mz"].dropna().to_numpy())

    # whole-spectrum coverage (TS bins explained vs unexplained, count + signal)
    if ts_path and os.path.exists(os.path.expanduser(ts_path)):
        from . import timeseries as TS
        ts = pd.read_parquet(os.path.expanduser(ts_path))
        if not ctx.get("batch_name") and "sample_batch_name" in ts.columns:
            names = ts["sample_batch_name"].dropna().unique()
            if len(names):
                ctx["batch_name"] = str(names[0])
        mat, bin_mz = TS.build_matrix(ts)
        binsig = mat.sum(axis=0)
        expl = ctx.get("expl_mz", np.array([]))

        def matched(mz, tol=8.0):
            i = np.searchsorted(expl, mz)
            return any(0 <= j < len(expl) and abs(expl[j] - mz) / mz * 1e6 <= tol
                       for j in (i - 1, i))
        ex = np.array([matched(float(bin_mz[b])) for b in mat.columns])
        ctx["ts"] = {"nbins": int(len(ex)), "expl_count": int(ex.sum()),
                     "expl_signal": float(binsig.values[ex].sum()),
                     "tot_signal": float(binsig.sum())}

    for key, fn in [("jitter", "jitter_summary.json"), ("batch", "batch_summary.json")]:
        p = f"{out_dir}/{fn}"
        if os.path.exists(p):
            ctx[key] = json.load(open(p))
    vk = f"{out_dir}/van_krevelen_full_{tag}.png"
    if os.path.exists(vk):
        ctx["fig"]["vk"] = vk           # single (scatter)
    # cluster figures are PAGED (clusters_<set>_<tag>_p<i>.png) — collect ALL pages
    for key, stem in [("changing", f"clusters_changing_{tag}"),
                      ("flat", f"clusters_flat_{tag}"),
                      ("unassigned", f"clusters_unassigned_{tag}")]:
        paged = sorted(glob.glob(f"{out_dir}/{stem}_p*.png"),
                       key=lambda s: int(s.rsplit("_p", 1)[1].split(".")[0]))
        if paged:
            ctx["fig"][key] = paged
        elif os.path.exists(f"{out_dir}/{stem}.png"):
            ctx["fig"][key] = [f"{out_dir}/{stem}.png"]
    cc = f"{out_dir}/clusters_changing_{tag}.csv"
    if os.path.exists(cc):
        ctx["changing_csv"] = pd.read_csv(cc)
    return ctx


# ---------------------------------------------------------------------------
# page helpers
# ---------------------------------------------------------------------------
def _close(pdf, fig):
    import matplotlib.pyplot as plt
    pdf.savefig(fig)
    plt.close(fig)


def _text_lines(fig, lines, *, x=0.08, y0=0.90, dy=0.026, size=10):
    """Render (style, text) lines top-down. style: 'h' head / 'b' body / 'm' mono."""
    y = y0
    for style, txt in lines:
        if style == "gap":
            y -= dy * (txt or 1)
            continue
        kw = dict(fontsize=size, color=INK, va="top", family="sans-serif")
        if style == "h":
            kw.update(fontsize=size + 3, weight="bold")
        elif style == "m":
            kw.update(family="monospace", fontsize=size - 0.5)
        elif style == "dim":
            kw.update(color=GREY, fontsize=size - 1)
        fig.text(x, y, txt, **kw)
        y -= dy
    return y


def _image_page(pdf, png, title, *, landscape=False, dpi=200, native=False, src_dpi=170):
    """Embed a PNG as one page. native=True makes the PAGE the image's own size
    (page = pixels/src_dpi inches) so a tall cluster figure embeds 1:1 and stays
    fully legible (the page is tall; scroll). Otherwise fit to A4 (landscape opt)."""
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt
    img = mpimg.imread(png)
    if native:
        ih, iw = img.shape[0] / src_dpi, img.shape[1] / src_dpi
        Th = 0.5 if title else 0.0                  # title strip (inches); the figures
        fig = plt.figure(figsize=(iw, ih + Th), dpi=src_dpi)   # carry their own title
        if title:
            fig.text(0.01, 1 - 0.20 / (ih + Th), title, fontsize=12, weight="bold",
                     color=INK, va="top")
        ax = fig.add_axes([0.005, 0.002, 0.99, ih / (ih + Th)])
        ax.imshow(img); ax.axis("off")
        pdf.savefig(fig); plt.close(fig)
        return
    figsize = (A4[1], A4[0]) if landscape else A4
    fig = plt.figure(figsize=figsize, dpi=dpi)
    if title:
        fig.text(0.04, 0.975, title, fontsize=13, weight="bold", color=INK)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.93] if title else [0.02, 0.02, 0.96, 0.96])
    ax.imshow(img); ax.axis("off")
    pdf.savefig(fig, dpi=dpi)
    plt.close(fig)


def _pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


# how each analyte ion is formed: bare (de)protonated, clustered with the reagent,
# or adducted with another small species.
_REAGENT_CLUSTER = {"[M+Br]-", "[M+HBr+Br]-", "[M+Br2]-", "[M+Br3]-", "[M+Cl]-",
                    "[M+I]-", "[M+I2]-", "[M+(CH4N2O)H]+"}
_OTHER_ADDUCT = {"[M+Na]+", "[M+NH4]+", "[M+CO3]-", "[M+HSO4]-"}


def _adduct_cat(a) -> str:
    a = str(a)
    if a in ("[M+H]+", "[M-H]-"):
        return "protonated / deprotonated"
    if a in _REAGENT_CLUSTER:
        return "reagent cluster"
    if a in _OTHER_ADDUCT:
        return "other adduct (Na/NH4/CO3)"
    return "other"


# ---------------------------------------------------------------------------
# sections  (each draws page(s); add/reorder freely)
# ---------------------------------------------------------------------------
def cover(ctx, pdf):
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=A4)
    batch = ctx.get("batch_name") or ctx["label"]
    fig.text(0.08, 0.93, "Peak Assignment Report", fontsize=20, weight="bold", color=INK)
    fig.text(0.08, 0.895, batch, fontsize=14, color=INK)
    fig.text(0.08, 0.872, f"{ctx['label']} · representative-sample pipeline", fontsize=11,
             color=GREY)
    meta = ctx.get("version", "")
    if ctx.get("generated"):
        meta = f"{meta}  ·  generated {ctx['generated']}" if meta else f"generated {ctx['generated']}"
    if meta:
        fig.text(0.08, 0.852, meta, fontsize=8.5, color=GREY)

    tiers = ctx["tiers"]; idn = tiers.get("Identified", 0); cn = tiers.get("Candidate", 0)
    ts = ctx.get("ts"); sig = (_pct(ts["expl_signal"], ts["tot_signal"]) if ts else None)
    ex_c = (_pct(ts["expl_count"], ts["nbins"]) if ts else None)
    head = [
        ("h", "Summary"),
        ("gap", 0.3),
        ("b", f"Unique analytes assigned (M0):   {ctx['n_m0']}   "
              f"({idn} Identified / {cn} Candidate)"),
        ("b", f"Distinct neutral compounds:       {ctx['n_neutrals']}"),
    ]
    if ts:
        head += [
            ("b", f"Spectral coverage:                {ex_c:.0f}% of m/z bins, "
                  f"{sig:.0f}% of signal explained"),
            ("b", f"Unexplained:                      {ts['nbins']-ts['expl_count']} bins "
                  f"({100-ex_c:.0f}% count, {100-sig:.0f}% signal)"),
        ]
    head += [
        ("gap", 1),
        ("h", "Representative samples assigned"),
        ("gap", 0.3),
        ("b", f"{ctx['n_files']} files: 5 evenly time-spaced + the max-TIC sample, "
              "merged by m/z."),
    ]
    for name, role in ctx.get("samples", [])[:8]:
        head.append(("m", f"   {name}   [{role}]"))
    j = ctx.get("jitter", {})
    if j:
        head += [
            ("gap", 1),
            ("h", "File-to-file reproducibility"),
            ("gap", 0.3),
            ("b", f"Per-file calibration spread:  {j.get('offset_spread_ppm','?')} ppm"),
            ("b", f"Mass jitter (median / p95):   {j.get('mz_jitter_raw_median','?')} / "
                  f"{j.get('mz_jitter_raw_p95','?')} ppm  (≈ genuine peak noise)"),
            ("b", f"Formula disagreements:        {j.get('formula_disagreements','?')}  "
                  "(same m/z, different formula across files)"),
            ("b", f"Tier-unstable assignments:    {j.get('tier_unstable','?')}  "
                  "(flip Identified <-> Candidate across files)"),
            ("dim", "On a disagreement/flip the merge keeps the highest tier, then the "
                    "highest match score."),
        ]
    _text_lines(fig, head, y0=0.80, dy=0.029)
    _close(pdf, fig)


def coverage(ctx, pdf):
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=A4)
    fig.text(0.08, 0.95, "Assignment quality", fontsize=15, weight="bold", color=INK)

    # (a) mean match score, Identified vs Candidate
    sbt = ctx.get("score_by_tier", {})
    tiers = [t for t in ("Identified", "Candidate") if t in sbt]
    ax = fig.add_axes([0.12, 0.62, 0.32, 0.26])
    ax.bar(tiers, [sbt[t] for t in tiers], color=["#1D9E75", "#E0A93B"][:len(tiers)], width=0.6)
    for i, t in enumerate(tiers):
        ax.text(i, sbt[t], f"{sbt[t]:.2f}", ha="center", va="bottom", fontsize=11)
    ax.set_ylim(0, 1.05); ax.set_ylabel("mean match score")
    ax.set_title("Match score by confidence", loc="left", fontsize=11)

    # (b) assignments by ion channel (how the analyte ion is formed)
    ad = ctx.get("adduct_cat", {})
    order = ["protonated / deprotonated", "reagent cluster", "other adduct (Na/NH4/CO3)", "other"]
    items = [(k, ad[k]) for k in order if ad.get(k)]
    short = {"protonated / deprotonated": "(de)protonated", "reagent cluster": "reagent\ncluster",
             "other adduct (Na/NH4/CO3)": "other adduct\n(Na/NH4/CO3)", "other": "other"}
    ax2 = fig.add_axes([0.56, 0.62, 0.36, 0.26])
    ax2.bar(range(len(items)), [v for _, v in items], color="#378ADD", width=0.6)
    for i, (_, v) in enumerate(items):
        ax2.text(i, v, str(v), ha="center", va="bottom", fontsize=10)
    ax2.set_xticks(range(len(items))); ax2.set_xticklabels([short.get(k, k) for k, _ in items], fontsize=8)
    ax2.set_ylabel("M0 count"); ax2.set_title("Assignments by ion channel", loc="left", fontsize=11)

    ts = ctx.get("ts")
    idn = ctx["tiers"].get("Identified", 0); cn = ctx["tiers"].get("Candidate", 0)
    lines = [("h", "Assigned vs unassigned"), ("gap", 0.3)]
    if ts:
        es = _pct(ts["expl_signal"], ts["tot_signal"])
        lines += [
            ("b", f"• Explained: {_pct(ts['expl_count'], ts['nbins']):.0f}% of m/z bins, "
                  f"{es:.0f}% of the ion signal."),
            ("b", f"• Unexplained: {ts['nbins'] - ts['expl_count']} bins — only {100 - es:.0f}% "
                  "of signal (dim, near-noise peaks)."),
        ]
    lines += [
        ("b", f"• {idn} Identified vs {cn} Candidate. Match score = the server "
              "isotope-scored compound match (0-1)."),
        ("b", "• Ion channel: (de)protonated = bare analyte ion; reagent cluster = adduct"),
        ("b", "  with the reagent ([M+Br]- etc.); other = Na/NH4/CO3 adduct."),
    ]
    _text_lines(fig, lines, y0=0.50, dy=0.030)
    _close(pdf, fig)


def composition(ctx, pdf):
    if "vk" in ctx["fig"]:
        _image_page(pdf, ctx["fig"]["vk"], "")          # figure carries its own title
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=A4)
    fig.text(0.08, 0.93, "Composition of the assigned peaks", fontsize=15, weight="bold", color=INK)
    comp = ctx.get("composition", {})
    het = ctx.get("hetero", {})
    lines = [("h", f"Distinct neutral compounds by backbone ({ctx['n_neutrals']} total)"),
             ("gap", 0.3)]
    for kl in ("CHO", "CHON", "CHOS"):
        if kl in comp:
            lines.append(("m", f"   {kl:6s} {comp[kl]}"))
    lines += [("gap", 1),
              ("h", "Heteroatom additions (within the backbone classes above)"),
              ("gap", 0.3)]
    for k, v in het.items():
        lines.append(("m", f"   {k:24s} {v}"))
    lines += [("gap", 1),
              ("dim", "Si/F/halogen are folded into the CHO/CHON/CHOS backbone, not split out"),
              ("dim", "(a siloxane with no N is CHO; a fluorinated species with N is CHON)."),
              ("dim", "Si = PDMS/silicone inlet bleed; F/halogen are reagent/contaminant ladders.")]
    _text_lines(fig, lines, y0=0.86, dy=0.030)
    _close(pdf, fig)


def families(ctx, pdf):
    for p in ctx["fig"].get("changing", []):
        _image_page(pdf, p, "", native=True)            # figure carries its own title
    cc = ctx.get("changing_csv")
    if cc is None or not len(cc):
        return
    import matplotlib.pyplot as plt
    from . import chemistry as C
    fig = plt.figure(figsize=A4)
    fig.text(0.08, 0.93, "Analyte families (temporal clusters)", fontsize=15, weight="bold", color=INK)
    sizes = cc.groupby("cluster").size().sort_values(ascending=False)
    big = [c for c in sizes.index if sizes[c] >= 3]      # only the PLOTTED clusters
    singletons = int((sizes < 3).sum())
    lines = [("h", f"Co-varying clusters ({len(big)} with >=3 members)"), ("gap", 0.3),
             ("m", "  cluster   n   median O/C   top members (by intensity)"),
             ("gap", 0.2)]
    for cid in big:
        g = cc[cc.cluster == cid]
        ocs = [cnt.get("O", 0) / cnt.get("C", 1) for cnt in
               (C.parse_formula(str(f)) for f in g["neutral_formula"]) if cnt.get("C", 0)]
        oc = np.median(ocs) if ocs else float("nan")
        top = ", ".join(g.sort_values("median_cps", ascending=False)["neutral_formula"].head(4))
        lines.append(("m", f"  {int(cid):>5}   {len(g):>2}     {oc:>5.2f}      {top}"))
    if singletons:
        lines += [("gap", 0.5),
                  ("dim", f"+ {singletons} singleton / <3-member peaks — shown together in the "
                          "last 'remaining peaks' panel of the changing-cluster figure.")]
    _text_lines(fig, lines, y0=0.86, dy=0.026, size=9)
    _close(pdf, fig)


def clusters(ctx, pdf):
    for p in ctx["fig"].get("flat", []) + ctx["fig"].get("unassigned", []):
        _image_page(pdf, p, "", native=True)            # figures carry their own titles


def methods(ctx, pdf):
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=A4)
    fig.text(0.08, 0.93, "Methods & caveats", fontsize=15, weight="bold", color=INK)
    lines = [
        ("h", "Pipeline"), ("gap", 0.3),
        ("b", "• Representative-sample rule: assign 5 evenly time-spaced samples + the"),
        ("b", "  max-TIC sample per batch, then merge by m/z — a single averaged file"),
        ("b", "  misses analytes present only part of the run."),
        ("b", "• Each file: multi-pass formula assignment, server isotope-scored matching"),
        ("b", "  (match_compounds), isotope-envelope completion, calibrated tiering."),
        ("b", "• Clusters: TIC/reagent-normalised log-correlation, complete-linkage at r>0.6"),
        ("b", "  on the full-batch time series (signed distance keeps anti-phase apart)."),
        ("gap", 1),
        ("h", "Peak roles"), ("gap", 0.3),
        ("b", "• M0 = an assigned compound's monoisotopic peak (the identification)."),
        ("b", "• iso_child = its isotope satellite (13C / 81Br / 37Cl ...)."),
        ("b", "• reagent = reagent-ion / reagent-cluster peaks (e.g. Br3-)."),
        ("b", "• artifact = instrument peaks (FT ringing / sidelobes of a bright peak)."),
        ("b", "• unexplained = no confident formula."),
        ("gap", 1),
        ("h", "Caveats"), ("gap", 0.3),
        ("b", "• Report coverage both by count and by signal — they differ a lot."),
        ("b", "• 'Unexplained' is dominated by small near-noise peaks (low signal)."),
        ("b", "• Confidence (Identified/Candidate) applies to M0 compounds only."),
        ("b", "• Mass-degenerate peaks can flip formula across files (see jitter)."),
    ]
    _text_lines(fig, lines, y0=0.86, dy=0.028)
    if ctx.get("generated"):
        fig.text(0.08, 0.06, f"mascope_assign · generated {ctx['generated']}", fontsize=8, color=GREY)
    _close(pdf, fig)


SECTIONS = [cover, coverage, composition, families, clusters, methods]


def build(out_dir: str, *, tag: str, label: str, ts_path: str | None = None,
          out_pdf: str | None = None, generated: str = "", batch_name: str | None = None,
          sections=SECTIONS) -> str:
    """Build the PDF report for one batch run. `out_dir` holds the run artifacts.
    `batch_name` titles the report (else taken from the TS, else the reagent label)."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages
    ctx = load_context(out_dir, tag=tag, label=label, ts_path=ts_path,
                       generated=generated, batch_name=batch_name)
    out_pdf = out_pdf or os.path.join(os.path.expanduser(out_dir), f"report_{tag}.pdf")
    with PdfPages(out_pdf) as pdf:
        for section in sections:
            try:
                section(ctx, pdf)
            except Exception as e:                       # one bad section must not kill the report
                import matplotlib.pyplot as plt
                fig = plt.figure(figsize=A4)
                fig.text(0.08, 0.9, f"[section '{section.__name__}' failed: {e}]",
                         fontsize=10, color="#B00020", wrap=True)
                _close(pdf, fig)
    return out_pdf
