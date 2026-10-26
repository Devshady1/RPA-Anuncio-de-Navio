"""Resultado confirmado de uma execucao do anuncio no OpenPort."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecucaoAnuncio:
    duv: str
    numero_requisicao: str = ""
