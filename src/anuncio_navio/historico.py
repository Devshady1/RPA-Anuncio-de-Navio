"""Historico mestre das fichas e pedidos de cadastro.

`data/historico.csv` guarda uma linha por ficha processada e e a fonte da
aba HISTORICO das fichas novas; `data/pedidos.csv` guarda os cadastros que
faltam no OpenPort (formato `data,tipo,texto`). Ambos sao append-only,
UTF-8, e recebem o cabecalho apenas na primeira linha.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

CABECALHO = ("data", "navio", "imo", "viagem", "duv", "resultado", "detalhe")
CABECALHO_PEDIDOS = ("data", "tipo", "texto")
FORMATO_DATA = "%d/%m/%Y %H:%M"


def _texto_data(quando: datetime | None) -> str:
    return (quando or datetime.now()).strftime(FORMATO_DATA)


def _acrescentar(path: Path, cabecalho: tuple[str, ...], linha: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    novo = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        if novo:
            escritor.writerow(cabecalho)
        escritor.writerow(linha)


def registrar(
    root,
    *,
    navio,
    imo,
    viagem,
    duv="",
    resultado="",
    detalhe="",
    quando=None,
) -> None:
    linha = (_texto_data(quando), navio, imo, viagem, duv, resultado, detalhe)
    _acrescentar(Path(root) / "data" / "historico.csv", CABECALHO, linha)


def linhas(root) -> list[tuple[str, ...]]:
    """Todas as linhas do historico, incluindo o cabecalho."""
    path = Path(root) / "data" / "historico.csv"
    if not path.exists():
        return [CABECALHO]
    with path.open(encoding="utf-8", newline="") as f:
        return [tuple(linha) for linha in csv.reader(f)]


def pedido(root, *, tipo, texto, quando=None) -> None:
    linha = (_texto_data(quando), tipo, texto)
    _acrescentar(Path(root) / "data" / "pedidos.csv", CABECALHO_PEDIDOS, linha)
