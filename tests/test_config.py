import json
from app.config import Config


def test_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DEFAULT_CONFIG_PATH", tmp_path / "config.json")
    c = Config.load()
    assert c.default_speed == 1.0
    assert c.default_volume == 100
    assert c.window_preset == "标准"
    assert c.geometry == "480x270+100+100"
    assert c.borderless is True and c.always_on_top is True


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DEFAULT_CONFIG_PATH", tmp_path / "config.json")
    c = Config.load()
    c.default_speed = 1.5
    c.cookie_path = "cookies.txt"
    c.recent_urls.append("https://www.bilibili.com/video/BV1GJ411x7h7")
    c.save()
    raw = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert raw["default_speed"] == 1.5
    c2 = Config.load()
    assert c2.cookie_path == "cookies.txt"
    assert c2.recent_urls[-1].endswith("BV1GJ411x7h7")
