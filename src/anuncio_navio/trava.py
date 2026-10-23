"""Trava de instancia unica do servico da ficha.

O arquivo guarda `<pid> <isoformat(timespec="seconds")>`. Um lock mais novo
que `validade_min` bloqueia uma segunda instancia; um lock mais velho (ou
ilegivel) e considerado abandonado e pode ser sobrescrito. A gravacao usa
um temporario + `os.replace` para nunca deixar o lock pela metade.
"""
from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime
from pathlib import Path


def _idade_min(texto: str, agora: float) -> float:
    partes = texto.split()
    if len(partes) < 2:
        raise ValueError("lock sem data")
    criado = datetime.fromisoformat(partes[1])
    return (agora - criado.timestamp()) / 60.0


def _gravar(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".servico-lock-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()} {datetime.now().isoformat(timespec='seconds')}")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def adquirir(path: Path, *, agora=None, validade_min: int = 120) -> bool:
    """Tenta criar/roubar o lock. False se outra instancia ainda estiver ativa."""
    path = Path(path)
    agora = time.time() if agora is None else agora
    if path.exists():
        try:
            texto = path.read_text(encoding="utf-8")
            if _idade_min(texto, agora) < validade_min:
                return False
        except (OSError, ValueError):
            pass
    try:
        _gravar(path)
    except OSError:
        return False
    return True


def liberar(path: Path) -> None:
    """Remove o lock; nao falha se ele ja nao existir."""
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
