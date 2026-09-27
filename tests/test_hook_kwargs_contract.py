"""The template's HOOK functions accept **kwargs.

brkraw passes a hook only the keyword arguments its functions accept; with
**kwargs the hook gets --hook-arg values and, from brkraw 0.6.0, the frame
selection of `brkraw convert --axis/--frames` (axis, frames)."""

import inspect

from brkraw_hook_template.hook import HOOK


def test_hook_exposes_the_three_functions():
    assert set(HOOK) == {"get_dataobj", "get_affine", "convert"}


def test_every_hook_function_accepts_kwargs():
    for name, func in HOOK.items():
        kinds = {p.kind for p in inspect.signature(func).parameters.values()}
        assert inspect.Parameter.VAR_KEYWORD in kinds, name
