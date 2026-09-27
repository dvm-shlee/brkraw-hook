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
