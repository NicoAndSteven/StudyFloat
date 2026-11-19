"""Dev-only end-to-end smoke: parse -> launch mpv -> verify playback -> controls -> close."""
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.player.errors import StudyFloatError
from app.player.mpv_controller import MpvController
from app.source.bilibili_parser import BilibiliParser
from app.source.url_validator import normalize_url
from app.window.geometry import geometry_for_preset

URL = "https://www.bilibili.com/video/BV1GJ411x7h7"


def run():
    url = normalize_url(URL)
    stream = BilibiliParser().parse(url)
    print("parsed:", stream.title[:30], "duration:", round(stream.duration or 0, 1),
          "audio:", bool(stream.audio_url), flush=True)

    p = MpvController("resources/mpv/mpv.exe", "studyfloat_" + uuid.uuid4().hex[:8],
                      "app/player/resources")
    try:
        p.start([
            f"--geometry={geometry_for_preset('标准')}",
            "--volume=100", "--speed=1.0", "--ontop", "--no-border",
            "--window-dragging=yes",
            "--http-header-fields=Referer: https://www.bilibili.com/",
        ])
        print("mpv started, pipe:", p.pipe_path, flush=True)
        p.command("loadfile", stream.video_url, "replace")

        ready = False
        for _ in range(20):
            try:
                if p.command("get_property", "path", timeout=1):
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(0.15)
        assert ready, "file did not load"
        print("file-loaded, path set", flush=True)

        if stream.audio_url:
            print("sending audio-add...", flush=True)
            p.command("audio-add", stream.audio_url)
            print("audio-add done", flush=True)
        p.command("set_property", "pause", False)
        print("unpaused", flush=True)
        p.command("set_property", "speed", 1.0)
        print("speed set", flush=True)
        p.command("set_property", "volume", 100)
        print("volume set", flush=True)

        time.sleep(2)
        print("slept", flush=True)
        t1 = p.command("get_property", "time-pos")
        print("time-pos after 2s:", round(t1 or 0, 2), flush=True)
        print("aid:", p.command("get_property", "aid"), "tracks:",
              p.command("get_property", "track-list/count"), flush=True)

        p.command("set_property", "speed", 1.5)
        print("speed:", p.command("get_property", "speed"), flush=True)
        p.command("seek", 5, "relative")
        time.sleep(0.5)
        t2 = p.command("get_property", "time-pos")
        print("time-pos after seek:", round(t2 or 0, 2), flush=True)
        p.command("set_property", "mute", True)
        print("mute:", p.command("get_property", "mute"), flush=True)
        p.command("set_property", "mute", False)

        assert (t2 or 0) > (t1 or 0), "playback did not advance"
        print("E2E PASS", flush=True)
    except StudyFloatError as exc:
        print("E2E FAIL:", exc, flush=True)
        raise
    finally:
        p.close()
        print("mpv closed", flush=True)


if __name__ == "__main__":
    run()
