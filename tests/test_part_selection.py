"""分P选择决策逻辑测试：合辑总是弹列表，即使 URL 带 ?p=N。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.source.bilibili_parts import PartInfo, decide_selection, requested_page

PARTS = [
    PartInfo(1, 111, "P1 title", 100),
    PartInfo(2, 222, "P2 title", 200),
    PartInfo(18, 333, "P18 title", 300),
]


def test_requested_page_extracts_p_from_url():
    assert requested_page("https://www.bilibili.com/video/BV1qG41197E4?p=18") == 18
    assert requested_page("https://www.bilibili.com/video/BV1qG41197E4?spm=a&p=2") == 2


def test_requested_page_none_when_absent_or_invalid():
    assert requested_page("https://www.bilibili.com/video/BV1qG41197E4") is None
    assert requested_page("https://www.bilibili.com/video/BV1qG41197E4?p=abc") is None


def test_decide_selection_multipart_with_p_still_shows_picker():
    """核心回归：合辑链接带 ?p=18 也必须弹列表，并高亮 P18。"""
    sel = decide_selection(PARTS, "https://www.bilibili.com/video/BV1qG41197E4?p=18")
    assert sel.show_picker is True
    assert sel.highlight_page == 18


def test_decide_selection_multipart_without_p_defaults_first_page():
    sel = decide_selection(PARTS, "https://www.bilibili.com/video/BV1qG41197E4")
    assert sel.show_picker is True
    assert sel.highlight_page == 1


def test_decide_selection_single_part_does_not_show_picker():
    sel = decide_selection([PartInfo(1, 111, "only", 10)], "https://www.bilibili.com/video/BV1qG41197E4?p=1")
    assert sel.show_picker is False


def test_decide_selection_p_out_of_range_falls_back_to_first():
    sel = decide_selection(PARTS, "https://www.bilibili.com/video/BV1qG41197E4?p=99")
    assert sel.show_picker is True
    assert sel.highlight_page == 1
