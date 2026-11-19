from app.window.geometry import PRESETS, geometry_for_preset, parse_geometry, save_geometry, load_geometry


def test_presets():
    assert PRESETS["微型"] == (320, 180)
    assert PRESETS["标准"] == (480, 270)


def test_geometry_for_preset():
    assert geometry_for_preset("标准", 100, 100) == "480x270+100+100"
    assert geometry_for_preset("自定义", 12, 34) == "480x270+12+34"


def test_parse_geometry():
    assert parse_geometry("640x360+12+34") == (640, 360, 12, 34)
    assert parse_geometry("1920x1080-5-10") == (1920, 1080, -5, -10)
    assert parse_geometry("garbage") is None
    assert parse_geometry(None) is None


def test_save_load_geometry_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.window.geometry.GEOMETRY_PATH", tmp_path / "geometry.json")
    assert load_geometry() is None
    save_geometry("640x360+12+34")
    assert (tmp_path / "geometry.json").read_text(encoding="utf-8").strip() == '"640x360+12+34"'
    assert load_geometry() == "640x360+12+34"
