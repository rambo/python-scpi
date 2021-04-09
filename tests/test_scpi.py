"""Package level tests"""
from scpi import __version__


def test_version() -> None:
    """Make sure version matches expected"""
    assert __version__ == "2.3.1"
