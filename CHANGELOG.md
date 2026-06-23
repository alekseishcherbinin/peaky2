# Changelog

All notable changes to Peaky are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 0.4.0 (public-release refactor)

A refactor pass preparing Peaky for the public `karsa-oy/peaky` repo: cleaner
install, enforced reproducibility, organized outputs, and a design doc.

### Added
- `docs/ARCHITECTURE.md` — the canonical design doc (ledger model, pass sequence,
  end-to-end data flow with diagram, reproducibility model, module map).
- `CHANGELOG.md` (this file).
- Legacy workspace-based Mascope server support (`io_mascope`): connects to older
  deployments where `/api/datasets` 404s, resolving workspaces/batches via the raw
  endpoints. Additive and gated — modern servers are unaffected.

### Changed
- **Import package renamed `mascope_assign` → `peaky`** (matching the dist + CLI
  name). A `mascope_assign` back-compat shim aliases the old import path — including
  submodules — to the same `peaky` objects, so existing `import mascope_assign`
  code keeps working unchanged. Version bumped to 0.4.0.
- **Single canonical lockfile.** Removed the hand-maintained `requirements.txt`
  (which had drifted from the real pins); `uv.lock` is now the only pinned source.
  `pip install -e .` uses the pyproject ranges; `uv sync` uses the exact pins. CI
  gains a `locked` job that enforces `uv.lock` with `uv sync --frozen`.
- Moved `ROADMAP.md` → `docs/ROADMAP.md` (kept as development history); README now
  points at `docs/ARCHITECTURE.md` as the entry point for how Peaky works.
- Repository URL → `github.com/karsa-oy/peaky` (the public home).

### Fixed
- **Reproducibility is now enforced, not just claimed.** The run driver exports the
  run's `when` as `SOURCE_DATE_EPOCH` (`pipeline.stamp_source_date_epoch`) before any
  rendering, so matplotlib stamps it into PNG/PDF metadata and the xlsx writer reads
  it via `cluster._resolve_when`. Two runs over the same inputs at the same `when` are
  now byte-identical across figures, PDF, and workbooks; a different `when` changes the
  bytes (the stamp tracks the run, like the Report ID). The single-sample report's
  "generated" cell honors the same variable. `test_determinism.py` now drives the real
  helper and asserts byte-stability for all three artifact types.
- `run_manifest.json` stores the input time-series path relative to the run dir (or
  absolute when referenced externally) instead of a bare basename, so it stays
  reproducible when the input TS is referenced rather than copied.
- Documented `cleanup.reclaim_envelope_tails` as a known no-op on real data (the leak it
  targets is absorbed upstream); kept but no longer implicitly trusted.

<!-- Filled in as the remaining phases land:
### Changed (outputs)     — run dir organized into figures/ tables/ report/; input time-series no longer copied per run.
-->
