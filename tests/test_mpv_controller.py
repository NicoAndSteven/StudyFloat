import json
import queue

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
        if isinstance(item, (dict, list)):
            return (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8")
        return item

    def close(self):
        self.closed = True


def make_controller():
    c = MpvController(mpv_path="mpv.exe", pipe_name="testpipe")
    c._pipe = FakePipe()
    return c, c._pipe


def _queue_response(pipe, request_index=0, error="success", data=None):
    msg = json.loads(pipe.written[request_index].decode())
    pipe.inbox.put({"request_id": msg["request_id"], "error": error, "data": data})


def test_command_returns_data():
    c, pipe = make_controller()
    import threading
    def answer():
        _queue_response(pipe, data=42)
    t = threading.Timer(0.02, answer)
    t.start()
    assert c.command("get_property", "time-pos") == 42


def test_command_raises_on_error():
    c, pipe = make_controller()
    import threading
    def answer():
        _queue_response(pipe, error="property unavailable")
    t = threading.Timer(0.02, answer)
    t.start()
    with pytest.raises(MpvCommandError):
        c.command("get_property", "nope")


def test_observe_receives_property_change():
    c, pipe = make_controller()
    seen = []
    c.observe("time-pos", lambda v: seen.append(v))
    import threading
    def answer():
        # response for the observe command, plus an event before a later command
        _queue_response(pipe, 0, data="success")
        pipe.inbox.put({"event": "property-change", "id": 1, "name": "time-pos", "data": 12.5})
        _queue_response(pipe, 1, data=None)
    t = threading.Timer(0.02, answer)
    t.start()
    c.command("get_property", "duration")
    assert seen == [12.5]


def test_start_builds_expected_command():
    from unittest.mock import patch

    with patch("app.player.mpv_controller.subprocess.Popen") as popen, \
         patch("app.player.mpv_controller.Path") as path:
        path.return_value.is_file.return_value = True
        c = MpvController(mpv_path="mpv.exe", pipe_name="sf1")
        with patch.object(c, "_connect"):
            c.start(["--geometry=480x270+100+100", "--ontop"])
    cmd = popen.call_args.args[0]
    assert cmd[0] == "mpv.exe"
    assert "--no-config" in cmd
    assert r"--input-ipc-server=\\.\pipe\sf1" in cmd
    assert "--geometry=480x270+100+100" in cmd
    assert "--ontop" in cmd
