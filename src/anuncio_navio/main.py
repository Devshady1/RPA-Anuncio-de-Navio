import logging
import time

from playwright.sync_api import sync_playwright

from . import browser, caminhos, trava
from . import navegacao, anuncio, status, relatorio, verificar
from .exceptions import AnuncioEmAndamentoError, AnuncioError, VerificacaoError
from .resultado import ExecucaoAnuncio

logger = logging.getLogger("anuncio.main")


def executar_um(config, dados: dict) -> ExecucaoAnuncio:
    lock = caminhos.logs_dir(config.project_root) / "anuncio.lock"
    if not trava.adquirir(lock):
        raise AnuncioEmAndamentoError(
            "Outro anúncio já está em execução. Aguarde a conclusão antes de iniciar outro."
        )
    try:
        return _executar_um(config, dados)
    finally:
        trava.liberar(lock)


def _executar_um(config, dados: dict) -> ExecucaoAnuncio:
    logger.info(f"Ambiente: {getattr(config, 'ambiente', '?')} — {config.url}")
    if status.ja_feito(config, dados):
        logger.info(f"Ja feito {dados['imo']}_{dados['viagem']}, pulando (anti-duplicidade).")
        return ExecucaoAnuncio(duv="duplicado")
    rel_path = relatorio.nova_rodada(config)
    headless = config.headless and not config.primeiro_plano
    with sync_playwright() as pw:
        bw = pw.chromium.launch(headless=headless, slow_mo=config.slow_mo_ms,
                                args=["--start-maximized"])
        ctx = bw.new_context(no_viewport=True)
        ctx.set_default_timeout(config.timeout_ms)
        browser.ao_nova_pagina(ctx)
        page = ctx.new_page()
        browser.maximizar(page)
        browser.bloquear(page)
        try:
            navegacao.login(page, config)
            navegacao.abrir_tela_2003(page, config)
            navegacao.novo_registro(page, config)
            duv = anuncio.criar_anuncio(page, config, dados)
            numero_requisicao = verificar.confirmado_na_2001(
                page, config, dados["imo"], dados.get("eta_data"),
                viagem=dados.get("viagem", ""), duv=duv,
                retornar_programacao=True,
            )
            if not numero_requisicao:
                relatorio.registrar(rel_path, f"NAO CONFIRMADO IMO={dados['imo']} Viagem={dados['viagem']} DUV={duv}")
                raise VerificacaoError("Anuncio nao localizado na 2001 no status esperado. OK nao marcado.")
            numero_requisicao = str(numero_requisicao)
            status.marcar_ok(config, dados, duv, numero_requisicao=numero_requisicao)
            relatorio.registrar(
                rel_path,
                f"OK REQUISICAO={numero_requisicao} IMO={dados['imo']} "
                f"Viagem={dados['viagem']} DUV={duv}",
            )
            return ExecucaoAnuncio(duv=duv, numero_requisicao=numero_requisicao)
        except AnuncioError as e:
            relatorio.registrar(rel_path, f"ERRO {dados.get('imo')}: {e}")
            raise
        finally:
            if not config.headless and config.primeiro_plano and (
                config.manter_aberto or config.manter_aberto_seg > 0
            ):
                if config.manter_aberto:
                    logger.info("Navegador mantido aberto p/ auditoria. Pressione Ctrl+C para fechar...")
                    try:
                        while True:
                            time.sleep(3600)
                    except KeyboardInterrupt:
                        logger.info("Auditoria encerrada pelo usuario. Fechando navegador...")
                else:
                    logger.info(f"Navegador aberto {config.manter_aberto_seg}s p/ auditoria...")
                    time.sleep(config.manter_aberto_seg)
            ctx.close()
            bw.close()
