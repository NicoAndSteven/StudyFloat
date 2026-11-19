"""Validation C: drive an mpv instance over the named pipe and print responses."""
import json
import sys
import time

PIPE = r"\\.\pipe\studyfloat_probe"


def connect(timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return open(PIPE, "r+b", buffering=0)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("mpv IPC pipe not available")


p = connect()
rid = 0


def cmd(*args):
    global rid
    rid += 1
    p.write((json.dumps({"command": list(args), "request_id": rid}) + "\n").encode("utf-8"))
    while True:
        msg = json.loads(p.readline().decode("utf-8"))
        if msg.get("request_id") == rid:
            print(args, "->", msg.get("error"), msg.get("data"))
            return msg


# state before
cmd("get_property", "pause")
cmd("get_property", "time-pos")
cmd("get_property", "duration")
cmd("get_property", "geometry")
cmd("get_property", "border")
cmd("get_property", "ontop")

# attach external audio (DASH: video-only was loaded at launch)
if len(sys.argv) > 1:
    cmd("audio-add", sys.argv[1], "external", "audio")
cmd("get_property", "aid")

# playback controls
cmd("set_property", "pause", True)
time.sleep(0.3)
cmd("get_property", "time-pos")
cmd("set_property", "pause", False)
cmd("seek", 5, "relative")
cmd("set_property", "speed", 1.5)
cmd("set_property", "volume", 60)
cmd("set_property", "mute", True)
cmd("set_property", "mute", False)
time.sleep(0.5)
cmd("get_property", "time-pos")

# window flags via IPC
cmd("set_property", "border", True)
time.sleep(0.2)
cmd("set_property", "border", False)
cmd("set_property", "ontop", False)
time.sleep(0.2)
cmd("set_property", "ontop", True)
print("IPC validation done")
