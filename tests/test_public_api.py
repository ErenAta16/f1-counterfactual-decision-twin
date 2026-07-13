"""Every name in apexmind.__all__ must actually be importable from the top level.

This is what a notebook user relies on (``from apexmind import ...``); a
typo or a stale entry here would silently break that surface.
"""

import apexmind


def test_all_exports_are_present_and_not_none() -> None:
    for name in apexmind.__all__:
        assert hasattr(apexmind, name), f"apexmind.__all__ lists {name!r} but it is not importable"
        assert getattr(apexmind, name) is not None


def test_no_duplicate_exports() -> None:
    assert len(apexmind.__all__) == len(set(apexmind.__all__))


def test_version_is_exported() -> None:
    assert apexmind.__version__ == "0.1.0"
