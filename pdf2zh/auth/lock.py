"""Simple exclusive file lock for concurrent OAuth token refresh."""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from types import TracebackType


class FileLock:
    """Exclusive lock stored as a sibling lock file."""

    def __init__(self, path: Path):
        self._path = path
        self._fp = None

    def __enter__(self) -> "FileLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self._path, "a+")
        try:
            import fcntl

            fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX)
        except ImportError:
            try:
                import msvcrt

                msvcrt.locking(self._fp.fileno(), msvcrt.LK_LOCK, 1)
            except Exception:
                warnings.warn(
                    "File locking unavailable; concurrent OAuth refresh may race"
                )
        except Exception:
            warnings.warn("File locking failed; concurrent OAuth refresh may race")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._fp is None:
            return
        try:
            import fcntl

            fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
        except ImportError:
            try:
                import msvcrt

                msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        except Exception:
            pass
        try:
            self._fp.close()
        finally:
            self._fp = None


def sibling_lock(auth_path: Path) -> FileLock:
    return FileLock(auth_path.with_suffix(auth_path.suffix + ".lock"))


def secure_write_json(path: Path, data: str) -> None:
    """Atomic-ish write; best-effort 0600 permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
