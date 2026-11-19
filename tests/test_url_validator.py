import pytest
from app.source.url_validator import normalize_url, InvalidUrl

BV = "BV1GJ411x7h7"


@pytest.mark.parametrize("raw", [
    BV,
    f"https://www.bilibili.com/video/{BV}",
    f"https://b23.tv/{BV}",
    f"  https://www.bilibili.com/video/{BV}/?p=1  ",
    f"www.bilibili.com/video/{BV}",
])
def test_normalize_ok(raw):
    assert normalize_url(raw) == f"https://www.bilibili.com/video/{BV}"


@pytest.mark.parametrize("raw", ["", "https://example.com/watch?v=1", "BV123", "av170001"])
def test_normalize_rejects(raw):
    with pytest.raises(InvalidUrl):
        normalize_url(raw)
