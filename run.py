"""Entry-point local — somente disco local, sem servidor."""
import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("ANUNCIO_ROOT", str(ROOT))

from anuncio_navio.config import Config, URL_QAS, URL_PROD
from anuncio_navio import wizard, status, fila_json
from anuncio_navio.main import executar_um

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("rpa")


def bloqueado_prod(cfg) -> bool:
    """Trava anti-PROD: browser real contra PRODUCAO exige PERMITIR_PROD=1.

    Retorna True se deve BLOQUEAR (sem abrir navegador). QAS sempre libera.
    """
    if cfg.ambiente == "QAS":
        return False
    if cfg.ambiente != "PRODUCAO":
        print(f"BLOQUEADO: ambiente nao reconhecido para a URL {cfg.url}.")
        logger.error(f"Bloqueio por URL nao reconhecida: {cfg.url}")
        return True
    if os.environ.get("PERMITIR_PROD") == "1":
        logger.warning("PERMITIR_PROD=1: operacao REAL contra PRODUCAO autorizada.")
        return False
    print("BLOQUEADO: URL de PRODUCAO sem PERMITIR_PROD=1. "
          "Use --ambiente qas (homologacao) ou exporte PERMITIR_PROD=1.")
    logger.error(f"Bloqueio anti-PROD: {cfg.url}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="RPA Anuncio Navio 2003 — terminal interativo")
    ap.add_argument("--interativo", action="store_true", help="pergunta campo a campo e executa")
    ap.add_argument("--fila", action="store_true", help="processa todos os JSONs pendentes em dados_rpa/ (sem input)")
    ap.add_argument("--json", default="", help="processa um arquivo JSON especifico (sem input)")
    ap.add_argument("--dados-rpa", default="", help="pasta de entrada (padrao: <ROOT>/dados_rpa)")
    ap.add_argument("--dry-run", action="store_true", help="só coleta e mostra resumo, sem abrir browser")
    ap.add_argument("--manter-aberto", action="store_true", help="mantém o navegador aberto após a validação (auditoria manual)")
    ap.add_argument("--status", action="store_true", help="mostra status.json local")
    ap.add_argument("--colar-email", default="", help="texto do e-mail colado (só referência visual)")
    ap.add_argument("--env", default=str(ROOT / ".env"), help="arquivo .env local")
    ap.add_argument("--ambiente", choices=["qas", "prod"], default="",
                    help="atalho de URL: qas (homologacao, padrao) ou prod (exige PERMITIR_PROD=1)")
    ap.add_argument("--url", default="", help="override total da OPENPORT_URL (prioridade maxima)")
    args = ap.parse_args()

    if args.manter_aberto:
        os.environ["MANTER_ABERTO"] = "1"
    if args.url:
        url_override = args.url
    elif args.ambiente == "qas":
        url_override = URL_QAS
    elif args.ambiente == "prod":
        url_override = URL_PROD
    else:
        url_override = None
    cfg = Config.from_env(dotenv_path=args.env if Path(args.env).exists() else None,
                          url_override=url_override)
    logger.info(f"Ambiente: {cfg.ambiente} — {cfg.url}")

    if args.status:
        print(status.resumo(cfg))
        return 0

    # --- NOVO: modo fila JSON (entrada principal; o metodo de insercao do QA pluga aqui) ---
    if args.fila or args.json:
        from pathlib import Path as _P

        if args.json:
            pendentes = [_P(args.json)]
        else:
            pasta = _P(args.dados_rpa) if args.dados_rpa else fila_json.pasta_dados(cfg.project_root)
            pendentes = fila_json.listar_pendentes(pasta)
        if not pendentes:
            print("Nenhum JSON pendente em dados_rpa/.")
            return 0
        if args.dry_run:
            ok, falhas = 0, 0
            for p in pendentes:
                try:
                    dados = fila_json.carregar_anuncio(p)
                    dest = fila_json.finalizar_dryrun(p)  # consome a fila p/ o monitor nao repetir
                    print(f"DRY-RUN OK {p.name}: IMO {dados['imo']} Viagem {dados['viagem']} -> {dest.name}")
                    ok += 1
                except Exception as e:
                    print(f"DRY-RUN ERRO {p}: {e}")
                    try:
                        fila_json.finalizar_erro(p, e)  # invalido vai p/ erro/, tambem sai da fila
                    except Exception:
                        pass
                    falhas += 1
            print(f"\nDRY-RUN concluido: {ok} ok, {falhas} erro(s).")
            return 0 if falhas == 0 else 1
        if not cfg.login or not cfg.senha:
            print("Configure OPENPORT_LOGIN/SENHA no .env local.")
            return 1
        if bloqueado_prod(cfg):
            return 2
        ok, falhas = 0, 0
        for p in pendentes:
            try:
                dados = fila_json.carregar_anuncio(p)  # <- substitui wizard.coletar()
                resultado = executar_um(cfg, dados)
                if resultado.duv == "duplicado":
                    # barrado pela anti-duplicidade: NAO foi anunciado. Vai para
                    # duplicados/ para nao sumir da fila como se fosse sucesso.
                    fila_json.finalizar_duplicado(p)
                    print(f"DUPLICADO {p.name}: ja anunciado antes (nao processado).")
                    falhas += 1
                else:
                    fila_json.finalizar_sucesso(p, resultado.duv)
                    print(
                        f"Concluido {p.name}. Requisicao="
                        f"{resultado.numero_requisicao} DUV={resultado.duv}"
                    )
                    ok += 1
            except Exception as e:
                logger.exception(f"Falha em {p}: {e}")
                try:
                    fila_json.finalizar_erro(p, e)
                except Exception:
                    pass
                falhas += 1
        print(f"\nFila concluida: {ok} ok, {falhas} erro(s).")
        return 0 if falhas == 0 else 1

    if not args.interativo and not args.dry_run:
        ap.print_help()
        print("\nUse: python run.py --interativo [--ambiente qas]  |  --fila [--ambiente qas]  |  --json dados_rpa/x.json  |  --dry-run  |  --status")
        return 0

    dados = wizard.coletar(cfg, colar_email=args.colar_email)
    if not dados:
        print("Cancelado.")
        return 0
    if args.dry_run:
        print("\nDRY-RUN OK (nada executado):", dados)
        return 0
    if not cfg.login or not cfg.senha:
        print("Configure OPENPORT_LOGIN/SENHA no .env local.")
        return 1
    if bloqueado_prod(cfg):
        return 2
    try:
        resultado = executar_um(cfg, dados)
        print(
            f"\nConcluido. Requisicao={resultado.numero_requisicao} "
            f"(Programacao). DUV={resultado.duv}"
        )
        return 0
    except Exception as e:
        logger.exception(f"Falha: {e}")
        print("\nAlgo saiu errado — confira logs/ + screenshots/. Corrigimos juntos.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
