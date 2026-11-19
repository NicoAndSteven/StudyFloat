from __future__ import annotations

import itertools
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from app.player.errors import MpvCommandError, PlayerStartError


class MpvController:
    """Owns one mpv subprocess and one JSON-IPC named-pipe connection.

    IPC is synchronous: command() writes one JSON request and reads lines until
    the matching response arrives. This avoids all reader-thread races on
    Windows named pipes. observe_property callbacks are dispatched inline
    whenever a command() drains an incoming event.
    """

    def __init__(self, mpv_path: str | Path, pipe_name: str, script_dir: Path | None = None):
        self.mpv_path = str(mpv_path)
        self.pipe_name = pipe_name
        self.script_dir = script_dir
        self.proc: subprocess.Popen | None = None
        self._pipe = None
        self._ids = itertools.count(1)
        self._observers: dict[int, Callable[[Any], None]] = {}
        self._observe_ids: dict[str, int] = {}
        self._pending_events: list[dict[str, Any]] = []
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
        self.proc = subprocess.Popen(
            cmd,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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

    def _send(self, payload: dict[str, Any]) -> None:
        self._pipe.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))

    def _read_message(self, timeout: float) -> dict[str, Any] | None:
        """Read one JSON line from the pipe. A raw FileIO has no read timeout,
        but mpv normally replies within milliseconds; we guard with a socket
        timeout on the underlying handle where available."""
        # Windows named pipes opened as files do not support settimeout(); the
        # command loop uses an overall deadline and mpv's replies are prompt.
        line = self._pipe.readline()
        if not line:
            return None
        try:
            return json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {}

    def _dispatch_event(self, msg: dict[str, Any]) -> None:
        if msg.get("event") == "property-change":
            cb = self._observers.get(msg.get("id"))
            if cb:
                try:
                    cb(msg.get("data"))
                except Exception:
                    pass
        elif msg.get("event") in ("file-loaded", "end-file", "playback-restart"):
            self._on_playback_event(msg)

    def _on_playback_event(self, msg: dict[str, Any]) -> None:
        """Hook for stream-expiry reload; overridden by the application layer."""
        pass

    def command(self, *args: Any, timeout: float = 5.0) -> Any:
        rid = next(self._ids)
        self._send({"command": list(args), "request_id": rid})
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._read_message(deadline - time.time())
            if msg is None:
                raise MpvCommandError("播放器连接已断开")
            if msg.get("request_id") == rid:
                if msg.get("error") != "success":
                    raise MpvCommandError(str(msg.get("error")))
                # flush any events that arrived just before this response
                for ev in self._pending_events:
                    self._dispatch_event(ev)
                self._pending_events.clear()
                return msg.get("data")
            if "event" in msg:
                self._dispatch_event(msg)
            elif "request_id" in msg:
                self._pending_events.append(msg)
        raise MpvCommandError("播放器响应超时")

    def observe(self, prop: str, callback: Callable[[Any], None]) -> None:
        """Register a property observer. Events are dispatched during command()."""
        if prop in self._observe_ids:
            self._observers[self._observe_ids[prop]] = callback
            return
        rid = next(self._ids)
        self._observe_ids[prop] = rid
        self._observers[rid] = callback
        self._send({"command": ["observe_property", rid, prop], "request_id": rid})

    def get_property(self, prop: str, timeout: float = 5.0) -> Any:
        return self.command("get_property", prop, timeout=timeout)

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.command("quit", timeout=2)
            except Exception:
                pass
        self._closed = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        try:
            if self._pipe:
                self._pipe.close()
        except OSError:
            pass
