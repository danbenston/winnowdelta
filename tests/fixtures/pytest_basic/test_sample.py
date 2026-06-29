def test_passes():
    assert 1 + 1 == 2


def test_fails_equality():
    result = 1 + 1
    assert result == 3


def test_errors():
    raise RuntimeError("kaboom")


def test_skipped():
    import pytest

    pytest.skip("not today")
