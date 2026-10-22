import contextlib
import logging
import os
import re

from . import browser, lookup_engine
from .exceptions import AnuncioError, LookupError

logger = logging.getLogger("anuncio.anuncio")


def _codigo_do_termo(termo: str) -> str:
    """Codigo que o proprio operador escreveu: '30010 - MARINAV' -> '30010'.

    Serve de fallback quando o popup do OpenPort nao resolve: digitar o
    codigo que o agente ja deu e melhor do que abortar a rodada.
    """
    t = str(termo or "").strip()
    achado = re.match(r"^([A-Za-z0-9]+)\s*[-–—:]", t)
    if achado and achado.group(1) != t:
        return achado.group(1)
    return t if t.isdigit() else ""


def _campos_lookup(d: dict) -> list[tuple[lookup_engine.CampoLookup, str, str]]:
    """Campos de classificacao preenchidos: (campo, termo do agente, codigo fallback).

    A ordem e a de lookup_engine.CAMPOS (a mesma do Bloco 3 antigo).
    """
    saida = []
    for campo in lookup_engine.CAMPOS:
        termo = (d.get(campo.chave) or "").strip()
        if not termo:
            continue
        fallback = (d.get(campo.chave + "_codigo") or "").strip() or _codigo_do_termo(termo)
        saida.append((campo, termo, fallback))
    return saida


def _usar_fallback(candidatos: list[dict], codigo_fallback: str) -> bool:
    """Se o codigo do CSV local pode ser usado depois de o popup falhar.

    So quando o popup NAO achou nenhum cadastro. Com candidatos, o popup
    achou e nao conseguiu escolher: escolher pelo CSV local seria adivinhar
    (e a copia local do cadastro e velha).
    """
    return not candidatos and bool(codigo_fallback)


def _pendencia(campo, termo: str, candidatos: list[dict]) -> str:
    """Texto da pendencia: o que o agente escreveu e o que o popup achou."""
    msg = f"{campo.rotulo} '{termo}' nao encontrado no cadastro"
    if candidatos:
        lista = "; ".join(
            f"{c.get('codigo', '')} {c.get('descricao', '')}".strip()[:60]
            for c in candidatos[:5])
        msg += f". Candidatos: {lista}"
    return msg


def _ler_duv(page, config) -> str:
    duv = ""
    with contextlib.suppress(Exception):
        duv = page.locator(config.css["duv"]).first.input_value().strip()
    return duv


def _clicar_confirmar(page, config) -> bool:
    """Clica Confirmar: seletor configurado ou botao pelo texto. Retorna se clicou."""
    for tentativa in (
        lambda: browser.acionar(page, config.css["btn_confirmar"]),
        lambda: page.get_by_role("button", name=re.compile("Confirmar", re.I)).first.evaluate("el => el.click()"),
    ):
        try:
            tentativa()
            return True
        except Exception:
            continue
    return False


def criar_anuncio(page, config, d: dict) -> str:
    c = config.css
    # Bloco 1 — IMO só numeracao + TAB, sem localizar
    browser.preencher(page, c["imo"], d["imo"], reter=False)
    page.keyboard.press("Tab")
    browser.esperar(page, 1500)
    try:
        nome = page.locator(c["navio_nome"]).first.input_value().strip()
    except Exception:
        nome = ""
    if nome:
        logger.info(f"Navio: {nome}")
    else:
        logger.warning(f"IMO {d['imo']} nao retornou Navio (segue p/ Verificar acusar).")
    browser.preencher(page, c["viagem"], d["viagem"])
    browser.selecionar(page, c["tipo_viagem"], d["tipo_viagem"])
    browser.selecionar(page, c["tipo_operacao"], d["tipo_operacao"])
    browser.selecionar(page, c["sentido"], d["sentido"])
    browser.selecionar(page, c["natureza"], d["natureza"])

    # Bloco 2 — datas
    for k in ("eta", "etb", "etc", "ets"):
        if d.get(f"{k}_data"):
            browser.preencher(page, c[f"{k}_data"], d[f"{k}_data"])
        if d.get(f"{k}_hora"):
            browser.preencher(page, c[f"{k}_hora"], d[f"{k}_hora"])

    # Bloco 3 — lookups. O popup de consulta do OpenPort e a fonte viva do
    # cadastro: o agente escreve o NOME (ou "30010 - MARINAV") e o popup
    # devolve o codigo. O CSV local so entra como fallback quando o popup
    # nao conhece o cadastro.
    pend = []
    for campo, termo, codigo_fallback in _campos_lookup(d):
        ok, cands = browser.resolver_lookup_popup(page, campo, termo)
        if not ok and _usar_fallback(cands, codigo_fallback):
            logger.info(f"  {campo.rotulo}: popup nao achou '{termo}', usando o codigo local {codigo_fallback}.")
            ok = browser.preencher_lookup(page, campo.seletor_visivel, campo.seletor_hidden,
                                          campo.seletor_lupa, codigo_fallback, campo.rotulo)
        if not ok:
            pend.append(_pendencia(campo, termo, cands))
    if pend:
        browser.screenshot(page, config.project_root, "lookup_pendente")
        logger.warning(f"Lookups nao resolvidos: {', '.join(pend)}")
        # barra ANTES do Gravar: o OpenPort so recusaria com "Armador Afretador
        # nao pode ficar vazio", que e mensagem de programador para o agente.
        raise LookupError("Lookups nao resolvidos: " + ", ".join(pend))

    # Bloco 4 — calado / mercadoria direto
    for k, cssk in (("calado_cheg_proa", "calado_cheg_proa"), ("calado_cheg_popa", "calado_cheg_popa"),
                    ("calado_sai_proa", "calado_sai_proa"), ("calado_sai_popa", "calado_sai_popa"),
                    ("qtd", "qtd_carga"), ("tons", "tons_prev")):
        if d.get(k):
            browser.preencher(page, c[cssk], d[k])

    # DUV = numero da viagem. Campo obrigatorio antes do Gravar, mas o numero
    # oficial e gerado pelo sistema (nao vai em papel nenhum), entao este valor
    # e apenas um identificador provisorio e deterministico para o anuncio.
    # NUNCA sorteado: numero aleatorio em registro de autoridade nao e
    # auditavel e quebrava a rastreabilidade (ja gravou DUV=99999, 74628...).
    duv_provisoria = str(d.get("viagem") or "").strip()
    if not duv_provisoria:
        logger.warning("Viagem vazia: #COD_DUV ficara vazio e o Gravar pode ser rejeitado.")
    else:
        browser.preencher(page, c["duv"], duv_provisoria)
        logger.info(f"DUV provisoria = viagem {duv_provisoria}")

    # Ordem exigida pelo OpenPort: Gravar -> Verificar (verificar antes trava 500021).
    # Verificar abre confirm "Deseja verificar..." -> auto-OK. Sem Confirmar anuncio.
    logger.info("Gravando...")
    browser.acionar(page, c["btn_gravar"])
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle")
    browser.esperar(page, 2500)

    # Handler persistente: aceita confirms e LOGA alertas (ex. 500021).
    browser.aceitar_dialogos(page, "anuncio")

    duv = _ler_duv(page, config)
    logger.info(f"Gravado. DUV={duv or '?'}")

    logger.info("Verificando inconsistencias (auto-OK no confirm)...")
    browser.acionar(page, c["btn_verificar"])
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle")
    browser.esperar(page, 3000)

    # Passo final opcional: CONFIRMAR o anuncio (finaliza no OpenPort).
    # Exige CONFIRMAR_ANUNCIO=1; sem ela, para no Verificar (rascunho p/ auditoria).
    # NAO regravar aqui: o Verificar deixa o anuncio em status Elaborado e o
    # OpenPort recusa qualquer alteracao (200301) - medido no QAS em 22/10/2026.
    # O Confirmar funciona direto, sem gravar de novo.
    if os.environ.get("CONFIRMAR_ANUNCIO") == "1":
        logger.info("Confirmando anuncio (CONFIRMAR_ANUNCIO=1)...")
        if _clicar_confirmar(page, config):
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle")
            browser.esperar(page, 3000)
            duv_novo = _ler_duv(page, config)
            if duv_novo:
                duv = duv_novo
        else:
            logger.warning("Botao Confirmar nao localizado; anuncio segue nao-confirmado.")

    if not duv:
        # _ler_duv() le o campo que nos mesmos acabamos de preencher, entao
        # vazio aqui significa que o proprio campo nao aceitou o valor.
        duv = duv_provisoria
        logger.warning(
            "Campo #COD_DUV nao reteve o valor no QAS; registrando a "
            "DUV provisoria da viagem como referencia local."
        )
    logger.info(f"Finalizado. DUV={duv or '(vazia)'}")
    with contextlib.suppress(Exception):
        browser.screenshot(page, config.project_root, "anuncio_final")
    return duv
