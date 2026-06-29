"""Scaffold smoke test: the package imports and exposes a version."""

import atlas_counsel


def test_package_imports_with_version():
    assert isinstance(atlas_counsel.__version__, str)
    assert atlas_counsel.__version__
