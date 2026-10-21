"""Numero sequencial de viagem (e DUV) por anuncio emitido.

A viagem antes era a constante "0000000" em toda parte, o que tornava a
chave de anti-duplicidade (status.chave = imo_viagem) identica para sempre:
a segunda viagem do mesmo navio era pulada e ainda arquivada como sucesso.
Com o numero incremental a chave passa a ser unica por anuncio.

    data/sequencia.json  ->  {"ultima": 42}
    proxima(root)        ->  "000043"

O mesmo numero e usado como DUV provisoria: o OpenPort exige o campo
#COD_DUV preenchido antes do Gravar, mas o numero oficial e gerado pelo
sistema (nao vai em papel nenhum). Enquanto a leitura do numero real nao
for implementada, usamos a viagem -- deterministico e auditavel, nunca
sorteado.

Numero queimado nao e reutilizado: se o agente cancelar depois de enviar,
o proximo anuncio recebe o seguinte. Isso e preferivel a reusar numero.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger("anuncio.sequencia")

ARQ_REL = "data/sequencia.json"
LARGURA = 6


def _caminho(root) -> Path:
    return Path(root) / ARQ_REL


def _ler(root) -> int:
    p = _caminho(root)
    if not p.exists():
        return 0
    try:
        return int(json.loads(p.read_text(encoding="utf-8")).get("ultima", 0))
    except (ValueError, TypeError, OSError):
        logger.warning(f"{ARQ_REL} ilegivel; reiniciando a sequencia em 0.")
        return 0


def _gravar(p: Path, ultima: int) -> None:
    """Escrita atomica: o produtor de entrada pode rerodar e ler no meio."""
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"ultima": ultima}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def atual(root) -> str:
    """Ultimo numero emitido, formatado (sem incrementar)."""
    return f"{_ler(root):0{LARGURA}d}"


def proxima(root) -> str:
    """Reserva e devolve o proximo numero de viagem. Persiste imediatamente."""
    n = _ler(root) + 1
    _gravar(_caminho(root), n)
    logger.info(f"Viagem/DUV reservada: {n:0{LARGURA}d}")
    return f"{n:0{LARGURA}d}"


def alinhar(root, minimo: int) -> None:
    """Garante que a sequencia nao retroceda abaixo de `minimo`.

    Use depois de restaurar/processos antigos: garante que um numero ja
    emitido nao volte a ser entregue de novo.
    """
    if _ler(root) < minimo:
        _gravar(_caminho(root), minimo)
        logger.info(f"Sequencia alinhada para {minimo:0{LARGURA}d}.")
