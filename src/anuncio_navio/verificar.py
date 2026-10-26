"""Verificacao de anuncio na tela 2001 (somente leitura).

A tela 2003 cria o anuncio; a tela 2001 lista a programacao resultante. Esta
verificacao filtra por ETA e status esperado, confere IMO/viagem na tabela, abre o
botao Modificar da linha localizada e confere o cabecalho do cadastro. A DUV
informada e apenas referencia de auditoria e nao bloqueia a confirmacao.
"""
import contextlib
import logging
import os
import re
import unicodedata
from datetime import date, datetime

from . import browser, navegacao
from .exceptions import VerificacaoError

logger = logging.getLogger("anuncio.verificar")

# Valores observados no <select id="sqlFLG_STATUS"> da tela 2001.
STATUS_2001 = {
    "anunciado": "2,00",
    "anuncio completo": "8,00",
    "programado": "3,00",
    "atracado": "4,00",
    "despachado": "5,00",
    "finalizado": "6,00",
    "cancelado": "7,00",
    "fundeado": "9,00",
    "reprogramado": "21,00",
    "reatracado": "22,00",
}

CABECALHOS_2001 = {
    "progr": ("progr", "programacao"),
    "imo": ("imo",),
    "navio": ("navio", "nome navio"),
    "viagem": ("viagem", "n da viagem", "no da viagem", "numero da viagem"),
    "eta": ("eta",),
    "status": ("status",),
    "duv": ("duv", "n da duv", "no da duv", "numero da duv"),
}


def _texto_ascii(valor: str) -> str:
    normalizado = unicodedata.normalize("NFKD", valor or "")
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _normalizar_rotulo(valor: str) -> str:
    valor = _texto_ascii(valor).lower()
    valor = re.sub(r"[^a-z0-9 ]+", " ", valor)
    return re.sub(r"\s+", " ", valor).strip()


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D+", "", valor or "")


def _data_filtro(eta) -> str:
    """Normaliza ETA para o formato aceito pelo filtro: DD/MM/AAAA."""
    if isinstance(eta, datetime):
        return eta.strftime("%d/%m/%Y")
    if isinstance(eta, date):
        return eta.strftime("%d/%m/%Y")
    texto = str(eta or "").strip()
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", texto)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    raise VerificacaoError(f"ETA invalida para verificar na 2001: {eta!r}")


def _valores_status_esperados(status_esperado) -> list[str]:
    if status_esperado is None:
        status_esperado = os.environ.get("STATUS_2001_ESPERADO", "Anunciado")
    candidatos = status_esperado if isinstance(status_esperado, (list, tuple, set)) else [status_esperado]
    valores = []
    for item in candidatos:
        texto = str(item or "").strip()
        if not texto:
            continue
        if texto in STATUS_2001.values():
            valores.append(texto)
            continue
        chave = _normalizar_rotulo(texto)
        if chave in STATUS_2001:
            valores.append(STATUS_2001[chave])
            continue
        raise VerificacaoError(f"Status 2001 desconhecido: {item!r}")
    if not valores:
        raise VerificacaoError("Nenhum status esperado informado para a 2001.")
    return valores


def _mapa_colunas(cabecalhos: list[str]) -> dict[str, int]:
    mapa = {}
    for pos, titulo in enumerate(cabecalhos):
        chave = _normalizar_rotulo(titulo)
        for coluna, variantes in CABECALHOS_2001.items():
            if coluna not in mapa and chave in variantes:
                mapa[coluna] = pos
    return mapa


def _linha_confere(celulas: list[str], mapa: dict[str, int], imo: str, eta: str,
                   valores_status: list[str], viagem: str = "", duv: str = "") -> bool:
    def celula(nome: str) -> str:
        return celulas[mapa[nome]] if nome in mapa and mapa[nome] < len(celulas) else ""

    if _somente_digitos(celula("imo")) != _somente_digitos(imo):
        return False
    try:
        if _data_filtro(celula("eta")) != eta:
            return False
    except VerificacaoError:
        return False
    valor_status = STATUS_2001.get(_normalizar_rotulo(celula("status")), "")
    if valor_status not in valores_status:
        return False
    if viagem and celula("viagem").strip() != str(viagem).strip():
        return False
    return True


def _cabecalho_confere(texto: str, progr: str, imo: str, status_texto: str) -> bool:
    progr = str(progr or "").strip()
    status_texto = str(status_texto or "").strip()
    if not progr or not _somente_digitos(imo) or not status_texto:
        return False
    padrao = (
        rf"{re.escape(progr)}\s*-\s*.*?\bIMO\b\s*"
        rf"{re.escape(_somente_digitos(imo))}\s*-\s*{re.escape(status_texto)}"
    )
    return re.search(padrao, texto or "", re.IGNORECASE | re.DOTALL) is not None


def _preencher_data(page, css: str, data: str) -> None:
    browser.preencher(page, css, data)
    page.locator(css).first.press("Tab")
    browser.esperar(page, 500)


def confirmado_na_2001(page, config, imo: str, eta, status_esperado=None,
                       viagem: str = "", duv: str = "",
                       retornar_programacao: bool = False) -> bool | str:
    """Confirma na 2001; opcionalmente retorna o numero da requisicao/programacao."""
    if not _somente_digitos(str(imo or "")):
        raise VerificacaoError("IMO ausente: verificacao 2001 cancelada antes de marcar OK.")
    data = _data_filtro(eta)
    valores_status = _valores_status_esperados(status_esperado)

    try:
        seletor = {
            nome: config.css.get(chave, "")
            for nome, chave in (
                ("filtrar", "btn_filtrar_2001"),
                ("tabela", "lista_2001"),
                ("modificar", "modificar_2001"),
                ("eta_ini", "eta_ini_2001"),
                ("eta_fim", "eta_fim_2001"),
                ("status", "status_2001"),
            )
        }
        if not all(seletor.values()):
            raise VerificacaoError("Seletores da 2001 ausentes em config.css.")
        navegacao.abrir_tela_2001(page, config)
        _preencher_data(page, seletor["eta_ini"], data)
        _preencher_data(page, seletor["eta_fim"], data)
        browser.selecionar(page, seletor["status"], valores_status[0])
        browser.acionar(page, seletor["filtrar"])
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle")
        browser.esperar(page, 4000)

        tabela = page.locator(seletor["tabela"]).first
        tabela.wait_for(state="visible", timeout=15000)
        cabeca = tabela.locator("thead tr")
        if cabeca.count():
            cabecalhos = [c.inner_text().strip() for c in cabeca.first.locator("th, td").all()]
            corpo = tabela.locator("tbody")
            linhas = corpo.locator("tr").all() if corpo.count() else tabela.locator("tr").all()[1:]
        else:
            linhas = tabela.locator("tr").all()
            if not linhas:
                logger.warning("2001 sem linhas na tabela de resultado.")
                return False
            cabecalhos = [c.inner_text().strip() for c in linhas[0].locator("th, td").all()]
            linhas = linhas[1:]
        if not linhas:
            logger.warning("2001 sem linhas de dados na tabela de resultado.")
            return False
        mapa = _mapa_colunas(cabecalhos)
        if "progr" not in mapa or "imo" not in mapa or "eta" not in mapa or "status" not in mapa:
            browser.screenshot(page, config.project_root, "verificacao_2001_layout")
            raise VerificacaoError(f"Colunas Progr/IMO/ETA/Status nao encontradas na 2001: {cabecalhos}")

        for numero, linha in enumerate(linhas, start=1):
            celulas = [c.inner_text().strip() for c in linha.locator("th, td").all()]
            if not any(celulas):
                continue
            if _linha_confere(celulas, mapa, str(imo), data, valores_status, viagem, duv):
                progr = celulas[mapa["progr"]].strip()
                status_texto = celulas[mapa["status"]].strip()
                duv_linha = celulas[mapa["duv"]] if "duv" in mapa else ""
                link = linha.locator(seletor["modificar"]).first
                if not progr or link.count() == 0:
                    browser.screenshot(page, config.project_root, "verificacao_2001_sem_modificar")
                    raise VerificacaoError("Linha localizada na 2001 sem Programacao/botao Modificar.")
                url_antes = page.url
                link.evaluate("el => el.click()")
                for _ in range(15):
                    browser.esperar(page, 1000)
                    url_atual = page.url or ""
                    if url_atual != url_antes and "cadastro.aspx" in url_atual:
                        break
                else:
                    browser.screenshot(page, config.project_root, "verificacao_2001_detalhe_nao_abriu")
                    raise VerificacaoError("Botao Modificar nao abriu o cadastro da programacao.")
                with contextlib.suppress(Exception):
                    page.wait_for_load_state("networkidle")
                browser.esperar(page, 2500)
                texto_detalhe = page.locator("body").first.inner_text()
                if not _cabecalho_confere(texto_detalhe, progr, str(imo), status_texto):
                    logger.warning(
                        "Cabecalho do cadastro nao confere: Progr=%s IMO=%s Status=%s.",
                        progr, _somente_digitos(str(imo)), status_texto,
                    )
                    browser.screenshot(page, config.project_root, "verificacao_2001_detalhe_divergente")
                    return False
                logger.info(
                    "Confirmado na 2001: Progr=%s IMO=%s ETA=%s Status=%s DUV_lista=%s DUV_ref=%s.",
                    progr, _somente_digitos(str(imo)), data, status_texto, duv_linha, duv,
                )
                browser.screenshot(page, config.project_root, "verificacao_2001_ok")
                return progr if retornar_programacao else True
        logger.warning(
            "Nao confirmado na 2001: IMO=%s ETA=%s status=%s.",
            _somente_digitos(str(imo)), data, ",".join(valores_status),
        )
        browser.screenshot(page, config.project_root, "verificacao_2001_nao_encontrado")
        return False
    except VerificacaoError:
        raise
    except Exception as e:
        browser.screenshot(page, config.project_root, "verificacao_2001_erro")
        raise VerificacaoError(f"Falha ao verificar na 2001: {type(e).__name__}: {e}") from e
