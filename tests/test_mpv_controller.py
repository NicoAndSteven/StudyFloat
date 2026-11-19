import json
import queue
import threading
import time
from unittest.mock import patch

import pytest

from app.player.errors import MpvCommandError
from app.player.mpv_controller import MpvController


class FakePipe:
    def __init__(self):
        self.written = []
        self.inbox = queue.Queue()
        self.closed = False

    def write(self, data):
        self.written.append(data)

    def readline(self):
        item = self.inbox.get(timeout=3)
        return (json.dumps(item) + "\n").encode("utf-8")

    def close(self):
        self.closed = True


def make_controller():
    pipe = FakePipe()
    c = MpvController(mpv_path="mpv.exe", pipe_name="testpipe")
    c._pipe = pipe
    c._start_reader()
    return c, pipe


def test_command_matches_request_id():
    c, pipe = make_controller()

    def answer():
        msg = json.loads(pipe.written[0].decode())
        pipe.inbox.put({"request_id": msg["request_id"], "error": "success", "data": 42})

    threading.Timer(0.05, answer).start()
    assert c.command("get_property", "time-pos") == 42


def test_command_raises_on_error():
    c, pipe = make_controller()

    def answer():
        msg = json.loads(pipe.written[0].decode())
        pipe.inbox.put({"request_id": msg["request_id"], "error": "property unavailable"})

    threading.Timer(0.05, answer).start()
    with pytest.raises(MpvCommandError):
        c.command("get_property", "nope")


def test_observe_receives_property_change():
    c, pipe = make_controller()
    seen = []
    c.observe("time-pos", lambda v: seen.append(v))
    pipe.inbox.put({"event": "property-change", "id": 1, "name": "time-pos", "data": 12.5})
    time.sleep(0.1)
    assert seen == [12.5]


def test_start_builds_expected_command():
    with patch("app.player.mpv_controller.subprocess.Popen") as popen, \
         patch("app.player.mpv_controller.Path") as path:
        path.return_value.is_file.return_value = True
        c = MpvController(mpv_path="mpv.exe", pipe_name="sf1")
        with patch.object(c, "_connect"):
            c.start(["--geometry=480x270+100+100", "--ontop"])
    cmd = popen.call_args.args[0]
    assert cmd[0] == "mpv.exe"
    assert "--no-config" in cmd
    assert "--input-ipc-server=\\\\.\\pipe\\sf1" in cmd
    assert "--geometry=480x270+100+100" in cmd
    assert "--ontop" in cmd
