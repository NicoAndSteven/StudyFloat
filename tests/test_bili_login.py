"""扫码登录核心逻辑测试（网络全部 mock，不依赖真实 B站）。"""
import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from app.source.bili_login import (
    LoginCancelled,
    LoginExpired,
    LoginPending,
    LoginResult,
    BiliQRLogin,
    cookies_to_netscape,
)


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def _session_with_responses(*responses):
    s = MagicMock()
    s.get.side_effect = [FakeResponse(r) for r in responses]
    return s


def test_generate_returns_url_and_key():
    login = BiliQRLogin.__new__(BiliQRLogin)
    login._session = _session_with_responses({
        "code": 0,
        "data": {"url": "https://scan.example/qr?key=abc", "qrcode_key": "abc"},
    })
    url, key = login.generate_qr()
    assert url == "https://scan.example/qr?key=abc"
    assert key == "abc"
    assert "qrcode/generate" in login._session.get.call_args.args[0]


def test_generate_raises_on_api_error():
    login = BiliQRLogin.__new__(BiliQRLogin)
    login._session = _session_with_responses({"code": -1, "message": "请求过于频繁"})
    with pytest.raises(RuntimeError, match="请求过于频繁"):
        login.generate_qr()


@pytest.mark.parametrize("code,exc", [
    (86101, LoginPending),
    (86090, LoginPending),
    (86038, LoginExpired),
])
def test_poll_pending_and_expired(code, exc):
    login = BiliQRLogin.__new__(BiliQRLogin)
    login._session = _session_with_responses({"data": {"code": code}})
    with pytest.raises(exc):
        login.poll("abc")


def test_poll_success_captures_cookies():
    login = BiliQRLogin.__new__(BiliQRLogin)
    resp = MagicMock()
    resp.json.return_value = {"data": {"code": 0, "url": "https://passport.bilibili.com/x/passport-login/login/success"}}
    resp.cookies = {"SESSDATA": "abc123", "bili_jct": "csrf1", "DedeUserID": "12345"}
    login._session = MagicMock()
    login._session.get.return_value = resp
    result = login.poll("abc")
    assert isinstance(result, LoginResult)
    assert result.cookies["SESSDATA"] == "abc123"
    assert "qrcode/poll" in login._session.get.call_args.args[0]


def test_cookies_to_netscape_format(tmp_path):
    out = tmp_path / "cookies.txt"
    cookies_to_netscape(
        {"SESSDATA": "abc%2F123", "bili_jct": "csrf", "buvid3": "B123infoc"},
        out,
    )
    text = out.read_text(encoding="utf-8")
    assert "# Netscape HTTP Cookie File" in text
    lines = [l for l in text.splitlines() if l and not l.startswith("#")]
    assert len(lines) == 3
    sess_line = next(l for l in lines if "SESSDATA" in l)
    parts = sess_line.split("\t")
    assert parts[0] == ".bilibili.com"
    assert parts[5] == "SESSDATA" and parts[6] == "abc%2F123"


def test_login_cancel_event_prevents_all_network_calls():
    login = BiliQRLogin.__new__(BiliQRLogin)
    login._session = MagicMock()
    stop = threading.Event()
    stop.set()
    with pytest.raises(LoginCancelled):
        login.login(on_qr=lambda url: None, stop_event=stop)
    login._session.get.assert_not_called()


def test_close_releases_session_and_is_idempotent():
    login = BiliQRLogin.__new__(BiliQRLogin)
    session = MagicMock()
    login._session = session
    login.close()
    session.close.assert_called_once()
    assert login._session is None
    login.close()
    session.close.assert_called_once()
