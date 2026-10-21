import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("anuncio.relatorio")


def nova_rodada(config) -> Path:
    d = config.project_root / "relatorios"
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.glob("rodada_*.log"))) + 1
    p = d / f"rodada_{n:03d}_{datetime.now():%Y%m%d_%H%M%S}.log"
    p.write_text(f"Rodada {n} {datetime.now():%d/%m/%Y %H:%M}\n", encoding="utf-8")
    return p


def registrar(path: Path, texto: str):
    with open(path, "a", encoding="utf-8") as f:
        f.write(texto + "\n")
    logger.info(texto)
