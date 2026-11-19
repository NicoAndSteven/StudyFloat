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
    """不带有效 p 参数或 p=1 时，规范化为干净的 BV URL。"""
    assert normalize_url(raw) == f"https://www.bilibili.com/video/{BV}"


def test_preserves_non_first_part_parameter():
    """多P视频必须保留 p>1 参数，否则 yt-dlp 会枚举整个合集导致卡死。"""
    raw = "https://www.bilibili.com/video/BV1qG41197E4/?spm_id_from=333&p=18"
    assert normalize_url(raw) == "https://www.bilibili.com/video/BV1qG41197E4?p=18"


def test_preserves_part_parameter_without_other_query():
    assert normalize_url("https://www.bilibili.com/video/BV1qG41197E4?p=3") == (
        "https://www.bilibili.com/video/BV1qG41197E4?p=3"
    )


@pytest.mark.parametrize("raw", ["", "https://example.com/watch?v=1", "BV123", "av170001"])
def test_normalize_rejects(raw):
    with pytest.raises(InvalidUrl):
        normalize_url(raw)
