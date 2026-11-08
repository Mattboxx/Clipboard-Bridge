"""Route desktop-environment shortcuts to the running app in the same login."""

import os
import socket
import stat
from pathlib import Path


COMMANDS = ("show", "toggle", "send", "receive")


def runtime_path():
    value = os.environ.get("XDG_RUNTIME_DIR", "")
    path = Path(value)
    if not value or not path.is_absolute():
        return None
    try:
        info = path.stat()
    except OSError:
        return None
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        return None
    return path / "clipboard-bridge.sock"


def forward(path, command):
    if path is None or command not in COMMANDS:
        return False
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
        client.settimeout(0.5)
        try:
            client.sendto(command.encode("ascii"), str(path))
        except OSError:
            return False
    return True


class ShortcutListener:
    def __init__(self, path):
        import fcntl

        self.path = path
        lock = path.with_suffix(".lock")
        self.lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self.socket = None
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path.unlink(missing_ok=True)
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.socket.bind(str(path))
            self.socket.setblocking(False)
        except BaseException:
            if self.socket is not None:
                self.socket.close()
            os.close(self.lock_fd)
            raise

    def take(self):
        try:
            command = self.socket.recv(16).decode("ascii", errors="replace")
        except BlockingIOError:
            return None
        return command if command in COMMANDS else None

    def close(self):
        self.socket.close()
        self.path.unlink(missing_ok=True)
        os.close(self.lock_fd)
