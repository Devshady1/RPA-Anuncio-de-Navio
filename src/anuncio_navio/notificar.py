"""Notificacao nativa do macOS via osascript.

Usada pelo servico invisivel para avisar o agente sem terminal. Fora do
macOS nao ha notificacao: apenas registra o aviso e devolve False.
Qualquer falha ao chamar o osascript tambem devolve False, para nunca
derrubar o ciclo da ficha.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys

logger = logging.getLogger("anuncio.notificar")


def notificar(
    titulo: str,
    texto: str,
    *,
    runner=subprocess.run,
    sistema: str | None = None,
) -> bool:
    sistema = sys.platform if sistema is None else sistema
    if not sistema.startswith("darwin"):
        logger.info(f"Notificacao ignorada em {sistema}: {titulo} - {texto}")
        return False
    script = (
        f"display notification {json.dumps(texto, ensure_ascii=False)}"
        f" with title {json.dumps(titulo, ensure_ascii=False)}"
    )
    try:
        runner(["osascript", "-e", script], check=False, capture_output=True)
    except Exception as exc:
        logger.warning(f"Falha ao notificar: {exc}")
        return False
    return True
