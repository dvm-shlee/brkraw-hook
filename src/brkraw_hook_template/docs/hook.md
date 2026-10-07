# Hook Template Overview

This package ships a starter hook that mirrors the brkraw-mrs layout.
The key assets that BrkRaw looks for are declared in `brkraw_hook.yaml`:

```yaml
docs: docs/hook.md
specs:
  - specs/info_template.yaml
  - specs/metadata_template.yaml
rules:
  - rules/template_rule.yaml
transforms:
  - transforms/template.py
# brkraw 0.6.0+: shared context maps (bases that a dataset's context map
# includes by `__meta__.name`); each file needs `__meta__.category:
# context_map`, `name` and `version`
# context_maps:
#   - context_maps/template_base.yaml
```

When the hook is installed via `brkraw hook install template`, the CLI loads
those files, evaluates the rules to pick specs/transforms, and finally calls
`brkraw_hook_template.hook:HOOK` to convert any supported scan. Installed
files go under a folder named after the package (`brkraw-hook-template`) in
the brkraw config folder, and `brkraw hook uninstall` removes them.

## brkraw 0.6.0 notes

- `get_dataobj` also receives the frame selection of `brkraw convert
  --axis/--frames` (`axis`, `frames`) through `**kwargs`; forward `**kwargs`
  to `helper.get_dataobj` as the template does.
- When `HOOK` has `convert`, brkraw passes the data as read, without its own
  per-frame slope/offset scaling (the same as 0.5.x). Scale in the hook if the
  output needs it. Without `convert`, brkraw 0.6.0 applies per-frame scaling
  itself.
- Context maps (0.6.0) name the output files; the hook still returns the
  image(s).

## Read-time options and memory protection (for hooks that reconstruct data)

The template hook only forwards `**kwargs` to `brkraw`'s default
`helper.get_dataobj`, which reads the frame selection (`axis`, `frames`) itself
and ignores keys it does not know. A hook that reconstructs data from raw
files (a slow step that can need a lot of memory) has to do more. The
reference implementation of the pattern below is **brkraw-sordino**
(`src/brkraw_sordino/hook.py`, `memguard.py`, `cacheio.py`; its options are
described in its `docs.md`). Copy the structure, not the SORDINO numbers.

### 1. Read-time options

Read-time options choose what is returned, not what is reconstructed. Accept
them through `**kwargs` of `get_dataobj` (and `get_dataobj_info`, below):

- `frames` and `axis`: the same rules as `brkraw convert --frames/--axis`. An
  int picks one frame and drops the frame axis, a list keeps the axis in that
  order, `"start:stop[:step]"` is a Python slice. sordino parses them with
  `brkraw.specs.context_map.output.parse_frames` (`_frame_selection` in its
  `hook.py`), so the rules stay the same as brkraw's. `axis` without `frames`
  is an error; a hook with one frame axis accepts `3`, `-1` or its axis name.
  Frames count the frames the hook reconstructs.
- `max_memory_gb`: float, the memory limit of the check below. Default: half of
  the physical memory (4 GB when it cannot be read).

Read-time options are not part of the cache key (section 4), so changing them
reads the same cache. Reconstruct the whole scan once, then read only the
selected frames from the cache (`cacheio.read_recon_frames`, one frame at a
time into one buffer).

### 2. Estimate first, then stop or go

Before it reconstructs or reads anything, the hook estimates the memory of what
it will return plus the working memory of the reconstruction step (when no
cache exists) and the disk space of a new cache. If the estimate is above the
limit, raise an error and do nothing else:

```python
class MyResourceError(MemoryError):          # sordino: memguard.SordinoResourceError
    def __init__(self, message, *, kind, info, retry_kwargs=None):
        super().__init__(message)
        self.kind = kind                      # "memory" or "disk"
        self.info = info                      # the estimate that was checked
        self.retry_kwargs = dict(retry_kwargs) if retry_kwargs else None
```

- Subclass `MemoryError`. The brkraw CLI (`brkraw convert`) catches a
  `MemoryError` that has a `retry_kwargs` dict; in a terminal it prints the
  message and asks `Proceed anyway with max_memory_gb=1.8 ...? [y/N]`, and on
  `y` converts once more with those hook arguments added. Without a terminal,
  with another answer, without `retry_kwargs`, or on a second stop, the error
  goes to the caller.
- `retry_kwargs` holds hook arguments that would pass the check. sordino gives
  `{"max_memory_gb": GB}` with the smallest limit in 0.1 GB steps that holds
  the estimate (`memguard.check`). A disk stop has no `retry_kwargs`: the fix
  is free space or another `cache_dir`.
- The message says how much is needed, the limit and where the limit comes
  from, that nothing was read or reconstructed, and what to ask for instead
  (fewer frames, or a higher limit).
- Keep the estimate deterministic (no measurement at run time) and conservative:
  fit it to measured runs (sordino pins its constants against measured rows in
  `tests/test_recon_memory_measured.py`) and state how far it is above them.
- Reconstruct in chunks so the working memory does not grow with the scan
  length. sordino cuts each frame into chunks of spokes, and the limit sets the
  chunk size (`memguard.recon_plan`); the check stops only when even the
  smallest chunk does not fit.

### 3. `get_dataobj_info`

Export `get_dataobj_info(scan, reco_id=None, **kwargs)` next to the hook
functions. It takes the same options as `get_dataobj` and returns the estimate
as a dict, without reading data, for callers (a viewer, a script) that decide
before loading. sordino returns `shape`, `dtype`, `count`, `nbytes`, `frames`,
`cached`, `cache_nbytes`, `peak_nbytes` (the number compared with the limit),
`limit_nbytes`, `limit_source`, `disk_nbytes`, `disk_free_nbytes` and some
step-specific keys; the full list is in its `docs.md`. Build `get_dataobj`
on the same planning function, so the information and the check cannot
disagree. `HOOK` itself needs only the functions brkraw calls
(`get_dataobj`, `get_affine`, optionally `convert`); `get_dataobj_info` is the
hook module's own public function.

### 4. Reconstruction cache

- Write the reconstruction once to a cache file under a `cache_dir` (sordino:
  `~/.brkraw/cache/sordino`, or under `BRKRAW_CONFIG_HOME`), next to a small
  `.json` with dtype and shape, and write to a `.partial` file that is renamed
  when finished.
- The cache key is the scan, reco, the data file identity and every option that
  changes the reconstructed values. List the options that only choose what is
  returned or cleaned up (sordino: `RECON_KEY_EXCLUDED`) and leave them out of
  the key. Every other option, including ones added later, stays in the key.
- Check a cache is valid before use (size equals shape times dtype size).
- Cache files stay for reuse until the user runs `brkraw cache clear`.

### 5. Checks to write

A hook that follows this pattern should test: the stop happens before any data
is read; `retry_kwargs` passes a second run; `get_dataobj_info` equals what
`get_dataobj` returns for the same options; a second run with a different
read-time option reads the cache without reconstructing again.

## Hook usage example

```bash
pip install .
brkraw hook install template
brkraw convert /path/to/source --output /path/to/output
```

Replace the stub conversion in `src/brkraw_hook_template/hook.py` with logic
that uses the provided `dataobj` and `affine` (or re-derives them) to produce
a NIfTI image (e.g. `nibabel.Nifti1Image`) or a compatible object supporting
`.to_filename()`.

## Rule / spec / transform example

The bundled rule file focuses on a placeholder metadata key. The rule maps
validation to the info + metadata specs before invoking the hook itself:

```yaml
converter_hook:
  - name: "template"
    when:
      scan_id:
        sources:
          - key: ScanIdentifier
    if:
      regex: ["$scan_id", "^TEMPLATE"]
    use: "template"
```

Keep your `rules/*.yaml` focused on detection logic. Keep `specs/*.yaml` as
source-to-target mappings, and keep all text/number sanitisation inside
`transforms/*.py`.
