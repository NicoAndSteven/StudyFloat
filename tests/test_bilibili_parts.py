"""B站合辑分P列表测试（mock 网络）。"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.source.bili_login import BiliQRLogin  # noqa: F401  (确保依赖可用)
from app.source.bilibili_parts import PartInfo, fetch_parts, is_multi_part, pick_part_url


VIEW_RESPONSE = {
    "code": 0,
    "data": {
        "aid": 408137669,
        "title": "计算机组成原理微课堂",
        "pages": [
            {"page": 1, "cid": 111, "part": "0 课程介绍", "duration": 338},
            {"page": 2, "cid": 222, "part": "1-1 计算机系统", "duration": 180},
            {"page": 18, "cid": 333, "part": "2-4-1 浮点数", "duration": 675},
        ],
    },
}


def _resp(json_data):
    r = MagicMock()
    r.json.return_value = json_data
    return r


def test_fetch_parts_parses_view_api():
    session = MagicMock()
    session.get.return_value = _resp(VIEW_RESPONSE)
    with patch("app.source.bilibili_parts._session", session):
        parts = fetch_parts("BV1qG41197E4")
    assert len(parts) == 3
    assert isinstance(parts[0], PartInfo)
    assert parts[0].page == 1 and parts[0].cid == 111
    assert parts[0].title == "0 课程介绍" and parts[0].duration == 338
    assert parts[2].page == 18


def test_fetch_parts_single_part_returns_one_entry():
    view = {"code": 0, "data": {"aid": 1, "title": "t", "pages": [
        {"page": 1, "cid": 1, "part": "only", "duration": 10},
    ]}}
    session = MagicMock()
    session.get.return_value = _resp(view)
    with patch("app.source.bilibili_parts._session", session):
        parts = fetch_parts("BV1qG41197E4")
    assert len(parts) == 1
    assert is_multi_part(parts) is False


def test_is_multi_part():
    assert is_multi_part([PartInfo(1, 1, "a", 1), PartInfo(2, 2, "b", 1)]) is True
    assert is_multi_part([PartInfo(1, 1, "a", 1)]) is False


def test_pick_part_url_preserves_bv_and_sets_p():
    parts = [PartInfo(1, 111, "a", 1), PartInfo(18, 333, "b", 1)]
    assert pick_part_url("https://www.bilibili.com/video/BV1qG41197E4", parts[1]) == (
        "https://www.bilibili.com/video/BV1qG41197E4?p=18"
    )


def test_fetch_parts_raises_on_api_error():
    session = MagicMock()
    session.get.return_value = _resp({"code": -404, "message": "啥都木有"})
    with patch("app.source.bilibili_parts._session", session):
        with pytest.raises(RuntimeError, match="啥都木有"):
            fetch_parts("BV1qG41197E4")
