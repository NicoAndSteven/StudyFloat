from __future__ import annotations

import itertools
import json
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from app.player.errors import MpvCommandError, PlayerStartError


class MpvController:
    """Owns one mpv subprocess and one JSON-IPC named-pipe connection."""

    def __init__(self, mpv_path: str | Path, pipe_name: str, script_dir: Path | None = None):
        self.mpv_path = str(mpv_path)
        self.pipe_name = pipe_name
        self.script_dir = script_dir
        self.proc: subprocess.Popen | None = None
        self._pipe = None
        self._ids = itertools.count(1)
        self._pending: dict[int, queue.Queue] = {}
        self._observers: dict[int, Callable[[Any], None]] = {}
        self._observe_ids: dict[str, int] = {}
        self._write_lock = threading.Lock()
        self._reader: threading.Thread | None = None
        self._closed = False

    @property
    def pipe_path(self) -> str:
        return rf"\\.\pipe\{self.pipe_name}"

    def start(self, launch_args: list[str]) -> None:
        if not Path(self.mpv_path).is_file():
            raise PlayerStartError(f"播放器不存在：{self.mpv_path}")
        cmd = [
            self.mpv_path,
            "--no-config",
            "--idle=yes",
            "--force-window=yes",
            "--keepaspect=yes",
            "--hwdec=auto-safe",
            "--osc=yes",
            f"--input-ipc-server={self.pipe_path}",
            *launch_args,
        ]
        if self.script_dir:
            script = Path(self.script_dir) / "studyfloat.lua"
            conf = Path(self.script_dir) / "input.conf"
            if script.is_file():
                cmd.insert(1, f"--script={script}")
            if conf.is_file():
                cmd.insert(1, f"--input-conf={conf}")
        self.proc = subprocess.Popen(cmd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._connect()

    def _connect(self, timeout: float = 8.0) -> None:
        end = time.time() + timeout
        while time.time() < end:
            try:
                self._pipe = open(self.pipe_path, "r+b", buffering=0)
                break
            except OSError:
                if self.proc and self.proc.poll() is not None:
                    raise PlayerStartError("播放窗口启动失败，请重试")
                time.sleep(0.1)
        else:
            raise PlayerStartError("连接播放窗口超时，请重试")
        self._start_reader()

    def _start_reader(self) -> None:
        self._reader = threading.Thread(target=self._read_loop, daemon=True, name="mpv-ipc-reader")
        self._reader.start()

    def _read_loop(self) -> None:
        while not self._closed:
            try:
                line = self._pipe.readline()
            except OSError:
                break
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if "request_id" in msg:
                q = self._pending.pop(msg["request_id"], None)
                if q:
                    q.put(msg)
            if msg.get("event") == "property-change":
                cb = self._observers.get(msg.get("id"))
                if cb:
                    try:
                        cb(msg.get("data"))
                    except Exception:
                        pass
            if msg.get("event") in ("file-loaded", "end-file", "playback-restart"):
                self._on_playback_event(msg)

    def _on_playback_event(self, msg: dict[str, Any]) -> None:
        """Hook for stream-expiry reload; overridden by the application layer."""
        pass

    def _send(self, payload: dict[str, Any]) -> None:
        with self._write_lock:
            self._pipe.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))

    def command(self, *args: Any, timeout: float = 5.0) -> Any:
        rid = next(self._ids)
        q: queue.Queue = queue.Queue()
        self._pending[rid] = q
        self._send({"command": list(args), "request_id": rid})
        try:
            msg = q.get(timeout=timeout)
        except queue.Empty as exc:
            self._pending.pop(rid, None)
            raise MpvCommandError("播放器响应超时") from exc
        if msg.get("error") != "success":
            raise MpvCommandError(str(msg.get("error")))
        return msg.get("data")

    def observe(self, prop: str, callback: Callable[[Any], None]) -> None:
        if prop in self._observe_ids:
            self._observers[self._observe_ids[prop]] = callback
            return
        rid = next(self._ids)
        self._observe_ids[prop] = rid
        self._observers[rid] = callback
        self._send({"command": ["observe_property", rid, prop], "request_id": rid})

    def close(self) -> None:
        self._closed = True
        try:
            if self._pipe:
                self._pipe.close()
        except OSError:
            pass
        if self.proc and self.proc.poll() is None:
            try:
                self.command("quit")
            except Exception:
                self.proc.terminate()
