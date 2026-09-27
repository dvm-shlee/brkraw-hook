# BrkRaw Hook Template

This repository is a template for implementing a BrkRaw dataset hook (rules/specs/transforms + Python hook entry points).

## Maintainer workflow (developers)
- Copy this template into a new repository, then update `pyproject.toml` metadata (name, entry point, dependencies) before publishing to PyPI.
- Implement the dataset-specific hook in `src/brkraw_hook_template/hook.py`. BrkRaw expects a `HOOK` dict that exposes `get_dataobj` and `get_affine` (and optionally `convert` for a richer workflow).
- Declare hook assets in `src/brkraw_hook_template/brkraw_hook.yaml`, which references package-local directories like `src/brkraw_hook_template/docs/`, `src/brkraw_hook_template/rules/`, `src/brkraw_hook_template/specs/`, and `src/brkraw_hook_template/transforms/`. With brkraw 0.6.0 or later the manifest can also list shared context maps (`context_maps:`); see `docs/hook.md`.
- Install in two steps: `pip install` the package, then `brkraw hook install <name>` registers its files with brkraw (`brkraw hook uninstall <name>` removes them).
- Use `src/brkraw_hook_template/docs/` as a writing template: define scope, document the rule/spec/transform flow, and record conversion notes and limitations.
- Keep `build-backend` on `setuptools`/`wheel`. BrkRaw still has fragile file-fetch paths when hooks rely on hatch-based installers.
- Optional maintainer tooling: `.vscode/tasks.json` contains release task placeholders, `.github/workflows/` contains CI/publish placeholders, and `tests/` contains a minimal hook install test.

## Hook architecture and data flow
- BrkRaw loads datasets via `from brkraw import load` (see `brkraw/src/brkraw/__init__.py`). The loader exposes `get_scan(scan_id)`; hook code should operate on BrkRaw `Scan` objects.
- `get_dataobj(scan, reco_id, **kwargs)` and `get_affine(scan, reco_id, space=..., **kwargs)` are called during conversion to resolve the raw data and spatial orientation.
- If conversion requires custom NIfTI assembly or multi-stage processing, implement `convert(scan, dataobj, affine, **kwargs)` and expose it via `HOOK`. This function receives the outputs of `get_dataobj` and `get_affine` and should return a NIfTI image object (or anything supporting `.to_filename()`).
- Always accept `**kwargs`. `brkraw convert` (see `brkraw/src/brkraw/cli/commands/convert.py`) forwards `--hook-arg name:key=value` into `hook_args_by_name={...}` and ultimately into your hook functions (e.g., `--hook-arg template:offset=5`). With brkraw 0.6.0 the frame selection (`--axis/--frames`) arrives the same way (`axis`, `frames`).
- If `HOOK` has `convert`, brkraw passes the data as read, without its per-frame slope/offset scaling (as in 0.5.x); scale in the hook when needed. Without `convert`, brkraw 0.6.0 scales per frame itself.
- Keep responsibilities separated: `rules/*.yaml` for detection/routing, `specs/*.yaml` for metadata mapping, `transforms/*.py` for sanitisation helpers. Document shared transforms in `src/brkraw_hook_template/docs/` (see `src/brkraw_hook_template/docs/rule_spec_transform.md`).


### Affine handling: match online reconstruction alignment

If your hook exposes `get_affine`, do not "simplify" the API. Prefer a thin wrapper that forwards BrkRaw's full `get_affine()` signature so downstream users can request the correct coordinate space and apply subject overrides consistently.

In particular, `get_affine` should accept and forward:

* `space` ("raw" | "scanner" | "subject_ras")
* `override_subject_type`, `override_subject_pose` (valid only for `space="subject_ras"`)
* `decimals`
* extra kwargs (for post-transforms like `flip_x/flip_y/flip_z`, `rad_x/rad_y/rad_z` if supported)

Recommended practice:

* **Do not invent a new affine resolver inside the hook.**
* Instead, follow the reference implementation in the main BrkRaw repo:
  `BrkRaw/brkraw -> src/brkraw/apps/loader/helper.py:get_affine`
* The goal is to ensure the hook output is aligned the same way as **online reconstruction (2dseq)**.

If you need a concrete validation pattern, see the example notebooks in `brkraw-sordino/notebooks` (they demonstrate how to sanity-check alignment against online recon outputs).



## Working with an AI agent

As AI-assisted development workflows continue to emerge, some contributors may choose to use AI agents when implementing or extending BrkRaw hooks.
This section provides practical guidance on how to do so **without breaking BrkRaw's extension model or hook contract**.

When prompting an AI agent, be explicit about the boundaries it must respect. In particular:

* In your prompt, point the agent to the base hook repository (`git@github.com:BrkRaw/brkraw-hook.git`) and to at least one real, working hook (for example `brkraw-mrs` or `brkraw-sordino`).

* Call out the non-negotiables: BrkRaw loads scans via `load()`, hook code must operate on `Scan` objects, and the hook must expose
  `HOOK = {'get_dataobj': ..., 'get_affine': ...}` (and `convert` only if required).

  ```python
  from brkraw import load

  loader = load("/path/to/source")
  scan = loader.get_scan(scan_id)
  # metadata resolution is usually handled via spec, not directly in the hook
  metadata = scan.get_metadata(reco_id=1)
  dataobj = scan.get_dataobj(reco_id=1)
  affine = scan.get_affine(reco_id=1)
  ```

* Make it clear that all hook options must be wired through `--hook-arg` (kwargs), not by inventing new CLI flags.

* If the workflow requires more than `get_dataobj` and `get_affine`, explicitly ask the agent to implement a **real** `convert()` method, not a placeholder.

A concrete example prompt that works well is:

> "Use `git@github.com:BrkRaw/brkraw-hook.git` as the base hook. Mimic `brkraw-mrs`: implement
> `HOOK = {'get_dataobj': ..., 'get_affine': ..., 'convert': ...}` in `hook.py`, operate on `Scan` objects from `brkraw.load(...).get_scan(scan_id)`, and use hook args (from `--hook-arg`) to enable optional preprocessing. Provide rule/spec/transform files that match the detection logic, and include a complete `convert()` implementation that returns a nibabel image."


## Notes
- Rules should be the first line of defense: keep them focused on scan identifiers, modality flags, or Bruker sequence/method markers, then route to the right spec/hook.
- `info_spec` drives the BrkRaw info parser (what appears in `brkraw info`), while `metadata_spec` feeds `get_metadata` and sidecar generation. Both should map raw headers to BrkRaw metadata keys and call into `transforms/` helpers for sanitisation (trim strings, convert units, inject constants).
- Document transforms that are shared between specs so future hooks can reuse them; check `src/brkraw_hook_template/docs/rule_spec_transform.md` for a general flow chart and template snippets.
- Tests should exercise the hook integration path (install the hook, ensure rules/specs/transforms register) rather than only unit-testing isolated helpers.
- The affine guidance is in "Affine handling" above.
