"""Limpeza de evidencias antigas (screenshots/, relatorios/, logs/).

Uso:
    python limpar_evidencias.py                # so MOSTRA o que apagaria (>30 dias)
    python limpar_evidencias.py --executar     # apaga de verdade
    python limpar_evidencias.py --dias 7       # outra janela de retencao

Sem `--executar` nada e apagado - e a forma segura de conferir antes.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%d/%m/%Y %H:%M:%S")
logger = logging.getLogger("limpeza")

PASTAS_PADRAO = ("relatorios", "screenshots", "logs")
# Nunca remover: rodape de auditoria da ultima execucao e modelos.
PRESERVAR = {"run_audit.bat", "streamlit.log", "streamlit.log.err"}


def _maiores_que(corte: datetime, pastas) -> list[Path]:
    achados = []
    for nome in pastas:
        pasta = ROOT / nome
        if not pasta.is_dir():
            continue
        for p in pasta.iterdir():
            if not p.is_file() or p.name in PRESERVAR:
                continue
            if datetime.fromtimestamp(p.stat().st_mtime) < corte:
                achados.append(p)
    return sorted(achados, key=lambda p: p.stat().st_mtime)


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove evidencias com mais de N dias.")
    ap.add_argument("--dias", type=int, default=30, help="janela de retencao (padrao: 30)")
    ap.add_argument("--pastas", nargs="*", default=list(PASTAS_PADRAO),
                    help=f"pastas a limpar (padrao: {' '.join(PASTAS_PADRAO)})")
    ap.add_argument("--executar", action="store_true",
                    help="sem esta flag o script so lista o que seria removido")
    args = ap.parse_args()

    corte = datetime.now() - timedelta(days=max(args.dias, 1))
    velhos = _maiores_que(corte, args.pastas)
    if not velhos:
        print(f"Nada com mais de {args.dias} dia(s) em: {', '.join(args.pastas)}.")
        return 0

    total = sum(p.stat().st_size for p in velhos) / 1e6
    print(f"{len(velhos)} arquivo(s), {total:.1f} MB, anteriores a "
          f"{corte:%d/%m/%Y} — em {', '.join(args.pastas)}:")
    for p in velhos:
        print(f"  {datetime.fromtimestamp(p.stat().st_mtime):%d/%m/%Y}  "
              f"{p.relative_to(ROOT)}")
    if not args.executar:
        print("\nNada apagado. Rode com --executar para limpar.")
        return 0
    for p in velhos:
        p.unlink()
    print(f"\n{len(velhos)} arquivo(s) removido(s), {total:.1f} MB liberados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
