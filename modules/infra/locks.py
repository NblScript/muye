"""Cross-platform file locking helpers."""

from __future__ import annotations

import platform

if platform.system() != "Windows":
    import fcntl
else:
    fcntl = None  # type: ignore[assignment]


def flock_ex(file) -> None:  # type: ignore[no-untyped-def]
    if fcntl is not None:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)


def flock_sh(file) -> None:  # type: ignore[no-untyped-def]
    if fcntl is not None:
        fcntl.flock(file.fileno(), fcntl.LOCK_SH)


def flock_un(file) -> None:  # type: ignore[no-untyped-def]
    if fcntl is not None:
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
