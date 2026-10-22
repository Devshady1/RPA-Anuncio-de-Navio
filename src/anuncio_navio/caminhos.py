"""Caminhos do deploy da ficha unica (Plano A).

Layout entregue ao usuario:

    <root>/ficha/ficha_anuncio_navio.xlsx   -> a unica ficha do agente
    <root>/ficha/arquivo/                   -> fichas preenchidas arquivadas
    <root>/data/                            -> estado (status, sequencia, historico)
    <root>/data/json/                       -> contrato de entrada do fila_json
    <root>/logs/                            -> logs do servico
    <root>/tmp/                             -> temporarios e trava de instancia
    <root>/config/.env                      -> credenciais do OpenPort

`home()` segue o mesmo significado de ANUNCIO_ROOT em config.from_env:
a raiz do deploy quando a variavel existe, senao a raiz do repositorio.
As funcoes com `root` sao puras: apenas montam o caminho, nunca criam pasta.
"""
from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    """Raiz do deploy: ANUNCIO_ROOT, ou a raiz do repo em desenvolvimento."""
    root_env = os.getenv("ANUNCIO_ROOT")
    if root_env:
        return Path(root_env).resolve()
    return Path(__file__).resolve().parents[2]


def ficha_dir(root: Path) -> Path:
    return Path(root) / "ficha"


def ficha(root: Path) -> Path:
    return ficha_dir(root) / "ficha_anuncio_navio.xlsx"


def arquivo_dir(root: Path) -> Path:
    return ficha_dir(root) / "arquivo"


def data_dir(root: Path) -> Path:
    return Path(root) / "data"


def logs_dir(root: Path) -> Path:
    return Path(root) / "logs"


def tmp_dir(root: Path) -> Path:
    return Path(root) / "tmp"


def json_dir(root: Path) -> Path:
    return data_dir(root) / "json"


def config_env(root: Path) -> Path:
    return Path(root) / "config" / ".env"
