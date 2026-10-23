"""Monitor da fila do RPA — dispara `run.py --fila` ao detectar JSON novo.

- Observa `dados_rpa/*.json` (glob nao-recursivo: ignora processados/, erro/ e
  pdfs/ automaticamente).
- Tambem observa a pasta `entrada/`: ficha preenchida (.xlsx) pelo agente
  maritimo. Cada ciclo converte as fichas em JSON da fila (`inserir.py`) e so
  depois dispara o RPA. Assim o anuncio nao depende de ninguem no chat.
- EXECUCAO REAL por padrao: o `--dry-run` ja foi validado em homologacao
  (anuncio do VOYAGER 9553256_000001 confirmado) e nao e mais o padrao.
  Use `--simular` para so validar sem abrir o browser.
- A trava anti-PRODUCAO continua independente, no `run.py`: URL de producao
  exige `PERMITIR_PROD=1`, entao ligar o monitor nao libera producao sozinho.
- Uso: `python monitor_fila.py [--intervalo 10] [--uma-vez] [--simular]`
- Servico da ficha unica (opt-in): `python monitor_fila.py --servico [--uma-vez]`
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DADOS_RPA = ROOT / "dados_rpa"
ENTRADA = ROOT / "entrada"

sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import caminhos, config, notificar, trava  # noqa: E402

MSG_OCUPADA = "Feche a planilha para o robô processar."
_SEM_NOTIFICACAO = object()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger("monitor")


def pendentes() -> list[Path]:
    """Lista JSONs na raiz de dados_rpa/ (ignora subpastas internas)."""
    DADOS_RPA.mkdir(parents=True, exist_ok=True)
    return sorted(DADOS_RPA.glob("*.json"))


def rodar_rpa(simular: bool = False) -> int:
    """Executa o runner e retorna o exit code (nunca levanta).

    Padrao: execucao real (`run.py --fila`), que e o caminho validado em
    homologacao. Com `simular=True` anexa `--dry-run`, que so valida os JSONs
    sem abrir o browser — util para conferir a fila antes de disparar.
    """
    cmd = [sys.executable, "run.py", "--fila"]
    if simular:
        cmd.append("--dry-run")
        logger.info("Modo simulacao (--simular): `run.py --fila --dry-run`.")
    else:
        logger.warning("Executando RPA REAL (abre o browser no ambiente configurado).")
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)
        return proc.returncode
    except Exception as e:  # ex.: falha ao spawnar processo
        logger.error(f"Falha ao disparar RPA: {type(e).__name__}: {e}")
        return 99


def ingerir_fichas(simular: bool = False) -> int:
    """Converte as fichas (.xlsx) de entrada/ em JSON da fila.

    Retorna quantas foram convertidas. Usa `inserir.py` por importacao, para
    valer a mesma regra de validacao/reserva de viagem do comando manual.
    """
    if not ENTRADA.exists():
        return 0
    fichas = sorted(ENTRADA.glob("*.xlsx"))
    if not fichas:
        return 0
    logger.info(f"{len(fichas)} ficha(s) em entrada/ — convertendo para a fila...")
    sys.path.insert(0, str(ROOT))
    try:
        from inserir import ingerir_pendentes
    except Exception as e:  # nao derruba o monitor por falha de import
        logger.error(f"Nao foi possivel carregar inserir.py: {type(e).__name__}: {e}")
        return 0
    try:
        resultados = ingerir_pendentes(ENTRADA, simular=simular)
    except Exception as e:
        logger.error(f"Falha ao converter fichas: {type(e).__name__}: {e}")
        return 0
    ok = sum(1 for r in resultados if r["ok"])
    ruins = [r for r in resultados if not r["ok"] and not r.get("travado")]
    travados = [r for r in resultados if r.get("travado")]
    for r in ruins:
        logger.warning(f"Ficha rejeitada: {r['arquivo'].name} — {r['erro'].splitlines()[0]}"
                       " (veja entrada/erro/)")
    for r in travados:
        logger.info(f"Ficha {r['arquivo'].name} continua em uso no Excel; "
                    "tentando no proximo ciclo.")
    return ok


def verificar_uma_vez(simular: bool = False) -> bool:
    """Uma passada: converte fichas, dispara o RPA se houver pendencia."""
    try:
        ingeridas = ingerir_fichas(simular=simular)
    except Exception as e:  # rede defensiva: loop nunca quebra por aqui
        logger.error(f"Erro inesperado na ingestao (seguindo): {type(e).__name__}: {e}")
        ingeridas = 0
    try:
        achados = pendentes()
    except Exception as e:
        logger.error(f"Erro ao ler {DADOS_RPA}: {type(e).__name__}: {e}")
        return False
    if not achados:
        logger.debug("Nenhum anuncio pendente.")
        return False
    logger.info(f"Novo anuncio detectado ({len(achados)} pendente(s), {ingeridas} ficha(s)"
                " convertida(s)). Disparando processamento do RPA...")
    try:
        rc = rodar_rpa(simular=simular)
    except Exception as e:  # rede defensiva: loop nunca quebra por aqui
        logger.error(f"Erro inesperado no disparo: {type(e).__name__}: {e}")
        return True
    if rc == 0:
        logger.info("RPA concluido com sucesso.")
    else:
        logger.warning(f"RPA terminou com codigo {rc} - verifique logs/ + dados_rpa/erro/.")
    return True


def _abrir_log_servico(root: Path) -> logging.FileHandler:
    destino = caminhos.logs_dir(root)
    destino.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(destino / "servico.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
    ))
    logging.getLogger().addHandler(handler)
    return handler


def _mtime_ficha(root: Path):
    try:
        return caminhos.ficha(root).stat().st_mtime
    except OSError:
        return None


def modo_servico(intervalo: float, uma_vez: bool, *, processar_fn=None,
                 dormir=time.sleep) -> int:
    """Loop do servico da ficha unica, protegido pela trava de instancia."""
    root = caminhos.home()
    handler = _abrir_log_servico(root)
    lock = caminhos.logs_dir(root) / "servico.lock"
    adquirida = False
    try:
        adquirida = trava.adquirir(lock)
        if not adquirida:
            logger.info(f"Outra instancia do servico esta ativa ({lock}); saindo.")
            return 0

        if processar_fn is None:
            from anuncio_navio import servico
            processar_fn = servico.processar

        cfg = config.Config.from_env(caminhos.config_env(root))

        if uma_vez:
            try:
                processar_fn(root, cfg)
            except KeyboardInterrupt:
                logger.info("Servico interrompido pelo usuario.")
            except Exception as e:
                logger.error(f"Erro no ciclo do servico: {type(e).__name__}: {e}")
            return 0

        logger.info(f"Servico da ficha unica ativo em {root} "
                    f"(a cada {intervalo:g}s)... (Ctrl+C para parar)")
        notificado_mtime = _SEM_NOTIFICACAO
        try:
            while True:
                try:
                    resultado = processar_fn(root, cfg)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Erro no ciclo do servico (seguindo): "
                                 f"{type(e).__name__}: {e}")
                else:
                    if getattr(resultado, "estado", "") == "ocupada":
                        mtime = _mtime_ficha(root)
                        if mtime != notificado_mtime:
                            notificar.notificar("Anúncio", MSG_OCUPADA)
                            notificado_mtime = mtime
                    else:
                        notificado_mtime = _SEM_NOTIFICACAO
                dormir(max(intervalo, 1))
        except KeyboardInterrupt:
            logger.info("Servico interrompido pelo usuario.")
            return 0
    finally:
        if adquirida:
            trava.liberar(lock)
        logging.getLogger().removeHandler(handler)
        handler.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Monitora dados_rpa/ e dispara o RPA a cada novidade.")
    ap.add_argument("--intervalo", type=float, default=10, help="segundos entre verificacoes (padrao: 10)")
    ap.add_argument("--uma-vez", action="store_true", help="uma unica verificacao e sai (p/ teste/cron)")
    ap.add_argument("--verbose", action="store_true", help="log discreto de 'sem pendencias' a cada ciclo")
    ap.add_argument("--simular", action="store_true",
                    help="so valida a fila (--dry-run), sem abrir o browser")
    ap.add_argument("--servico", action="store_true",
                    help="servico da ficha unica (trava de instancia + loop)")
    args = ap.parse_args()

    if args.servico:
        return modo_servico(args.intervalo, args.uma_vez)

    logger.info(f"Monitorando {DADOS_RPA} (e convertendo fichas de {ENTRADA}) "
                f"a cada {args.intervalo:g}s... (Ctrl+C para parar)")
    if args.uma_vez:
        verificar_uma_vez(simular=args.simular)
        return 0
    while True:
        try:
            disparou = verificar_uma_vez(simular=args.simular)
            if not disparou and args.verbose:
                logger.info("Sem pendencias. Continuando monitoramento...")
        except KeyboardInterrupt:
            logger.info("Monitor interrompido pelo usuario.")
            return 0
        except Exception as e:  # loop nunca quebra: rede, disco, etc.
            logger.error(f"Erro no ciclo do monitor (seguindo): {type(e).__name__}: {e}")
        try:
            time.sleep(max(args.intervalo, 1))
        except KeyboardInterrupt:
            logger.info("Monitor interrompido pelo usuario.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
