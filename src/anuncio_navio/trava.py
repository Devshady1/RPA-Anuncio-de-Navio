"""Trava de instancia unica do servico usando locks do sistema operacional."""
from __future__ import annotations

import errno
import os
import threading
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_handles: dict[Path, object] = {}
_handles_guard = threading.Lock()


def _tentar_bloquear(arquivo) -> None:
    if os.name == "nt":
        arquivo.seek(0)
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _desbloquear(arquivo) -> None:
    if os.name == "nt":
        arquivo.seek(0)
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)


def adquirir(path: Path) -> bool:
    """Adquire lock exclusivo não bloqueante; o SO o libera se o processo morrer."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _handles_guard:
        if path in _handles:
            return False
        arquivo = path.open("a+b")
        try:
            if path.stat().st_size == 0:
                arquivo.write(b"\0")
                arquivo.flush()
            _tentar_bloquear(arquivo)
            arquivo.seek(0)
            arquivo.truncate()
            arquivo.write(f"{os.getpid()}\n".encode("ascii"))
            arquivo.flush()
            os.fsync(arquivo.fileno())
            _handles[path] = arquivo
            return True
        except OSError as exc:
            arquivo.close()
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK, errno.EPERM):
                return False
            raise


def liberar(path: Path) -> None:
    """Libera o lock do sistema; o arquivo permanece como ponto de lock estável."""
    path = Path(path).resolve()
    with _handles_guard:
        arquivo = _handles.pop(path, None)
        if arquivo is None:
            return
        try:
            _desbloquear(arquivo)
        finally:
            arquivo.close()
