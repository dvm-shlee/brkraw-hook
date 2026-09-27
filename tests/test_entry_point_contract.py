"""Check the installed template against the public converter-hook contract."""

from importlib import metadata

from brkraw.specs.hook import resolve_hook


def test_template_entry_point_resolves():
    entries = [
        ep for ep in metadata.distribution("brkraw-hook-template").entry_points
        if ep.group == "brkraw.converter_hook" and ep.name == "template"
    ]
    assert len(entries) == 1
    assert resolve_hook("template") == entries[0].load()
