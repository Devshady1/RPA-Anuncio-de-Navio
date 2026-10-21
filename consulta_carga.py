"""Consulta rapida de MERCADORIA: nome -> codigo NCM (usa o resolvedor do RPA).

Uso:
    python consulta_carga.py niquel
    python consulta_carga.py "cacau em po"      # ambiguo: lista as opcoes

A resolucao e a MESMA do anuncio (tabelas.resolver_carga): aceita nome ou
codigo, ignora acento e plural, prefere o minerio e NUNCA devolve codigo de
residuo/desperdicio. Quando o nome e ambiguo, lista as opcoes para voce
escolher - nao adivinha.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("ANUNCIO_ROOT", str(ROOT))

from anuncio_navio import tabelas  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 0
    termo = " ".join(sys.argv[1:])
    codigo, candidatos = tabelas.resolver_carga(termo)
    if codigo:
        print(f"{termo} -> {codigo}")
        print(f"  {tabelas.descricao('carga', codigo)}")
        return 0

    if not candidatos:
        print(f"'{termo}': nenhuma mercadoria encontrada.")
        print("Pode ser mercadoria ainda nao cadastrada na tabela (cargas.csv).")
        return 1

    print(f"'{termo}' tem mais de uma opcao - escolha com o responsavel:")
    for cod, desc in candidatos:
        print(f"  {cod}  |  {desc}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
