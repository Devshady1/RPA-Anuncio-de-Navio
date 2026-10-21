"""Converte a FICHA preenchida (.xlsx) em JSON da fila do RPA.

Fluxo sem depender de chat (decisao de 14/10/2026):
    agente maritimo grava a ficha preenchida na pasta `entrada/`
      -> monitor (ou este comando) converte para dados_rpa/{IMO}_{VIAGEM}.json
      -> `run.py --fila` / `monitor_fila.py` executa o anuncio sozinho.

A planilha convertida vai para `entrada/processados/`; a rejeitada vai para
`entrada/erro/` com um `.log.txt` dizendo o motivo. A VIAGEM/DUV so e reservada
DEPOIS que a ficha passa na validacao - ficha invalida nao queima numero.

Uso:
    python inserir.py entrada\\ficha_do_agente.xlsx   # uma ficha
    python inserir.py entrada                          # todas da pasta
    python inserir.py entrada --simular                # so valida, nao converte
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("ANUNCIO_ROOT", str(ROOT))

from anuncio_navio import fila_json, planilha, sequencia  # noqa: E402

ENTRADA_PADRAO = ROOT / "entrada"
DESTINO_PADRAO = ROOT / "dados_rpa"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("inserir")


def _carimbo() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ingerir_um(arquivo: Path, destino: Path | None = None,
               processados: Path | None = None, root: Path | None = None,
               simular: bool = False) -> dict:
    """Converte uma ficha em JSON na fila.

    Ordem importante: a planilha SAI de `entrada/` antes de qualquer validacao
    ou reserva de viagem. Assim, se o agente ainda estiver com a ficha aberta
    no Excel, o arquivo fica onde esta (resultado `travado`) e o proximo ciclo
    tenta de novo - sem gerar JSON duplicado e sem queimar numero de viagem.

    Devolve {"ok", "arquivo", "json", "erro", "destino", "travado"}.
    """
    destino = Path(destino or DESTINO_PADRAO)
    root = Path(root or ROOT)
    pasta = Path(arquivo).parent
    processados = Path(processados or pasta / "processados")
    erros_dir = pasta / "erro"
    staging = pasta / ".processando"
    res = {"ok": False, "arquivo": Path(arquivo), "json": None, "erro": "",
           "destino": None, "travado": False}

    if simular:
        try:
            campos = planilha.ler_planilha(arquivo)
            erros = planilha.validar_campos(campos)
            if erros:
                raise ValueError("Ficha rejeitada:\n- " + "\n- ".join(erros))
            payload = planilha.construir_payload(campos)
            res.update(ok=True, destino=payload)
        except Exception as e:
            res["erro"] = f"{type(e).__name__}: {e}"
            logger.error("Ficha %s rejeitada: %s", arquivo.name, res["erro"])
        return res

    # 1) tira da fila de entrada ANTES de reservar numero (Excel pode estar aberto)
    staging.mkdir(parents=True, exist_ok=True)
    em_uso = staging / f"{arquivo.stem}__{_carimbo()}.xlsx"
    try:
        shutil.move(str(arquivo), str(em_uso))
    except PermissionError as e:
        res.update(travado=True,
                   erro=f"arquivo ainda aberto no Excel ({e}); tentando no proximo ciclo")
        logger.warning("Ficha %s continua em uso — sera reprocessada.", arquivo.name)
        return res

    # 2) valida e converte (so aqui a viagem e reservada)
    try:
        campos = planilha.ler_planilha(em_uso)
        erros = planilha.validar_campos(campos)
        if erros:
            raise ValueError("Ficha rejeitada:\n- " + "\n- ".join(erros))
        payload = planilha.construir_payload(campos)
        payload["viagem"] = sequencia.proxima(root)
        alvo = destino / f"{payload['imo']}_{payload['viagem']}.json"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        conferido = fila_json.carregar_anuncio(alvo)  # o proprio leitor precisa aceitar
        res.update(ok=True, json=alvo, destino=conferido)
        logger.info("Ficha %s -> %s (viagem %s, carga %s)",
                    arquivo.name, alvo.name, conferido["viagem"], conferido["carga"])
    except Exception as e:
        res["erro"] = f"{type(e).__name__}: {e}"
        logger.error("Ficha %s rejeitada: %s", arquivo.name, res["erro"])

    # 3) arquiva a planilha (sucesso ou erro)
    if res["ok"]:
        processados.mkdir(parents=True, exist_ok=True)
        fim = processados / f"{em_uso.stem}.xlsx"
    else:
        erros_dir.mkdir(parents=True, exist_ok=True)
        fim = erros_dir / f"{em_uso.stem}_ERRO.xlsx"
    shutil.move(str(em_uso), str(fim))
    if res["ok"]:
        res["json"].with_suffix(".origem.txt").write_text(f"Gerado de {fim.name}\n",
                                                          encoding="utf-8")
    else:
        fim.with_suffix(".log.txt").write_text(res["erro"] + "\n", encoding="utf-8")
    return res


def ingerir_pendentes(pasta: Path | None = None, destino: Path | None = None,
                      root: Path | None = None, simular: bool = False) -> list[dict]:
    """Processa todos os .xlsx da pasta de entrada (nao-recursivo)."""
    pasta = Path(pasta or ENTRADA_PADRAO)
    if not pasta.exists():
        return []
    return [ingerir_um(p, destino=destino, root=root, simular=simular)
            for p in sorted(pasta.glob("*.xlsx"))]


def main() -> int:
    ap = argparse.ArgumentParser(description="Converte ficha (.xlsx) em JSON da fila do RPA.")
    ap.add_argument("origem", nargs="?", default=str(ENTRADA_PADRAO),
                    help="arquivo .xlsx ou pasta com fichas (padrao: entrada/)")
    ap.add_argument("--dados-rpa", default="", help="pasta de destino da fila (padrao: dados_rpa)")
    ap.add_argument("--simular", action="store_true",
                    help="so valida as fichas: nao converte, nao move, nao reserva viagem")
    args = ap.parse_args()

    destino = Path(args.dados_rpa) if args.dados_rpa else DESTINO_PADRAO
    alvo = Path(args.origem)
    if alvo.is_file():
        resultados = [ingerir_um(alvo, destino=destino, simular=args.simular)]
    elif alvo.is_dir():
        resultados = ingerir_pendentes(alvo, destino=destino, simular=args.simular)
        if not resultados:
            print(f"Nenhuma ficha (.xlsx) em {alvo}.")
            return 0
    else:
        print(f"Nao encontrado: {alvo}")
        return 1

    ok = [r for r in resultados if r["ok"]]
    ruins = [r for r in resultados if not r["ok"]]
    for r in ok:
        print(f"OK    {r['arquivo'].name} -> {r['json'].name}"
              f"{'  [simulado]' if args.simular else ''}")
    for r in ruins:
        print(f"ERRO  {r['arquivo'].name}: {r['erro'].splitlines()[0]}")
    print(f"\n{len(ok)} convertida(s), {len(ruins)} rejeitada(s).")
    return 0 if not ruins else 1


if __name__ == "__main__":
    raise SystemExit(main())
