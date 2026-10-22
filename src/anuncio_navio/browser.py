import contextlib
import logging
import re
import time
from datetime import datetime

from playwright.sync_api import Page, BrowserContext

from . import lookup_engine

logger = logging.getLogger("anuncio.browser")


class FalhaPopup(RuntimeError):
    """Falha TECNICA no popup de consulta (nao e "nao encontrado").

    Quando o popup nao abre ou a grade/filtro nao podem ser lidos, nao da
    para saber se o cadastro existe. Devolver "nao encontrado" aqui faria o
    anuncio cair calado no CSV velho - o certo e a rodada falhar e repetir.
    """

_BLOQUEIO = """() => {
  if (window.__rpaBloq) return; window.__rpaBloq = true;
  ["mousedown","mouseup","click","dblclick","mousemove","contextmenu","wheel"].forEach(n =>
    document.addEventListener(n, e => { if (e.isTrusted) { e.stopImmediatePropagation(); e.preventDefault(); } }, true));
}"""


def esperar(page: Page, ms=1200):
    page.wait_for_timeout(ms)


def maximizar(page: Page):
    with contextlib.suppress(Exception):
        page.bring_to_front()
    try:
        cdp = page.context.new_cdp_session(page)
        wid = cdp.send("Browser.getWindowForTarget")["windowId"]
        cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "maximized"}})
    except Exception:
        pass


def bloquear(page: Page):
    with contextlib.suppress(Exception):
        page.evaluate(_BLOQUEIO)


def ao_nova_pagina(context: BrowserContext):
    def _h(p: Page):
        with contextlib.suppress(Exception):
            p.wait_for_load_state("domcontentloaded")
        bloquear(p)
    context.on("page", _h)


def preencher(page: Page, css: str, valor: str, reter: bool = False):
    loc = page.locator(css).first
    if reter:
        with contextlib.suppress(Exception):
            loc.evaluate("el => el.removeAttribute('onblur')")
    loc.scroll_into_view_if_needed()
    loc.focus()
    loc.fill(str(valor or ""))
    esperar(page, 300)


def selecionar(page: Page, css: str, value: str):
    loc = page.locator(css).first
    loc.scroll_into_view_if_needed()
    loc.select_option(value=str(value))
    esperar(page, 400)


def acionar(page: Page, css: str):
    loc = page.locator(css).first
    loc.scroll_into_view_if_needed()
    loc.evaluate("el => el.click()")
    esperar(page, 800)


def _hidden_valor(page: Page, css_hidden: str) -> str:
    try:
        return page.locator(css_hidden).first.input_value().strip()
    except Exception:
        return ""


def preencher_lookup(page: Page, css_visivel: str, css_hidden: str, css_lupa: str = "", codigo: str = "", rotulo=""):
    """Fill + TAB/Enter (ajaxLookup); se nao resolver, fallback via lupa-popup.

    Fallback (padrao do video manual): clica a lupa -> popup CONSULTA DE...
    -> filtra pelo Codigo -> seleciona o resultado -> confere o hidden.
    Retorna True se o hidden resolveu.
    """
    if not codigo:
        return True
    for tentativa, tecla in (("TAB", "Tab"), ("Enter", "Enter")):
        preencher(page, css_visivel, codigo, reter=False)
        page.keyboard.press(tecla)
        # polling do hidden (ajax pode demorar em tabelas grandes como mercadoria)
        hv = ""
        for _ in range(6):
            esperar(page, 1000)
            hv = _hidden_valor(page, css_hidden)
            if hv:
                break
        if hv:
            logger.info(f"  {rotulo} {codigo} -> hidden {hv[:20]} (via {tentativa})")
            return True
        # confere se o visivel foi limpo pelo onblur (sinal de nao-resolucao)
        try:
            vis = page.locator(css_visivel).first.input_value().strip()
        except Exception:
            vis = "?"
        logger.info(f"  {rotulo} {codigo}: tentativa {tentativa} sem hidden (visivel='{vis[:20]}'), retentando...")
    # --- fallback lupa-popup ---
    logger.info(f"  {rotulo} {codigo}: partindo p/ lupa-popup...")
    try:
        if _resolver_via_lupa(page, css_visivel, css_lupa, codigo, rotulo):
            hv = _hidden_valor(page, css_hidden)
            if hv:
                logger.info(f"  {rotulo} {codigo} -> hidden {hv[:20]} (via lupa)")
                return True
    except Exception as e:
        logger.warning(f"  {rotulo} {codigo}: lupa-popup falhou ({type(e).__name__}: {e})")
    logger.warning(f"  {rotulo} {codigo} nao resolveu (nem via lupa). Sera acusado no Verificar.")
    return False


def _raiz_projeto():
    import os
    from pathlib import Path
    return Path(os.environ.get("ANUNCIO_ROOT", "."))


def _achar_botao_lupa(page: Page, css_visivel: str, css_lupa: str):
    """Localiza o botao lupa: seletor explicito ou botao/imagem na mesma linha."""
    if css_lupa:
        try:
            cand = page.locator(css_lupa).first
            if cand.count() > 0:
                return cand
        except Exception:
            pass
    linha = page.locator(css_visivel).first.locator("xpath=ancestor::tr[1]")
    for sel in ("input[type=image]", "button", "input[type=button]", "img", "a"):
        try:
            cand = linha.locator(sel).first
            if cand.count() > 0 and cand.is_visible():
                return cand
        except Exception:
            continue
    return None


def _resolver_via_lupa(page: Page, css_visivel: str, css_lupa: str, codigo: str, rotulo: str) -> bool:
    """Clica a lupa, filtra por codigo no popup e seleciona o resultado."""
    botao = _achar_botao_lupa(page, css_visivel, css_lupa)
    if botao is None:
        logger.warning(f"  {rotulo}: botao lupa nao localizado.")
        return False
    botao.scroll_into_view_if_needed()
    try:
        with page.expect_popup(timeout=10000) as pop_info:
            botao.evaluate("el => el.click()")
        popup = pop_info.value
    except Exception:
        logger.warning(f"  {rotulo}: nenhum popup apos clicar a lupa.")
        return False
    try:
        popup.set_default_timeout(12000)
        esperar(popup, 1500)
        with contextlib.suppress(Exception):
            screenshot(popup, _raiz_projeto(), f"lupa_{rotulo}_aberta")
        # 1) filtra pelo Codigo (primeiro text input dos criterios)
        preenchido = False
        for loc in (
            popup.locator("input[type=text]").first,
            popup.locator("input:not([type])").first,
        ):
            try:
                if loc.count() > 0:
                    loc.fill(codigo)
                    preenchido = True
                    break
            except Exception:
                continue
        if not preenchido:
            logger.warning(f"  {rotulo}: campo de filtro nao achado no popup.")
            with contextlib.suppress(Exception):
                popup.close()
            return False
        # 2) clica Filtrar
        clicou = False
        for sel in (
            "input[value='Filtrar']",
            "button:has-text('Filtrar')",
            "input[value='Pesquisar']",
            "button:has-text('Pesquisar')",
        ):
            try:
                el = popup.locator(sel).first
                if el.count() > 0:
                    el.evaluate("el => el.click()")
                    clicou = True
                    break
            except Exception:
                continue
        if not clicou:
            popup.keyboard.press("Enter")
        esperar(popup, 2500)
        with contextlib.suppress(Exception):
            screenshot(popup, _raiz_projeto(), f"lupa_{rotulo}_resultado")
        # 3) seleciona o resultado: radio da 1a linha + botao de confirmacao
        selecionou = False
        try:
            radio = popup.locator("input[type=radio]").first
            if radio.count() > 0:
                radio.evaluate("el => el.click()")
                esperar(popup, 1000)
                for sel in (
                    "input[value='Selecionar']",
                    "button:has-text('Selecionar')",
                    "input[value='OK']",
                    "button:has-text('OK')",
                    "input[value='Confirmar']",
                    "button:has-text('Confirmar')",
                    "input[value='Escolher']",
                    "button:has-text('Escolher')",
                ):
                    try:
                        el = popup.locator(sel).first
                        if el.count() > 0:
                            el.evaluate("el => el.click()")
                            selecionou = True
                            break
                    except Exception:
                        continue
                if not selecionou:
                    # popups legados costumam fechar com duplo clique na linha
                    try:
                        lin = radio.locator("xpath=ancestor::tr[1]")
                        lin.evaluate("el => el.click()")
                        lin.evaluate("el => el.click()")
                        selecionou = True
                    except Exception:
                        pass
        except Exception:
            pass
        if not selecionou:
            logger.warning(f"  {rotulo}: resultado nao selecionavel no popup.")
            with contextlib.suppress(Exception):
                popup.close()
            return False
        # 4) aguarda popup fechar (callback preenche a tela principal)
        with contextlib.suppress(Exception):
            popup.wait_for_event("close", timeout=8000)
        with contextlib.suppress(Exception):
            if not popup.is_closed():
                popup.close()
        esperar(page, 2000)
        return True
    except Exception as e:
        logger.warning(f"  {rotulo}: erro no popup ({type(e).__name__}: {e})")
        with contextlib.suppress(Exception):
            popup.close()
        return False


_JS_GRADE = """() => {
  const rows = [...document.querySelectorAll('table#TQuery tr')].filter(tr => tr.querySelector('td'));
  return rows.map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()));
}"""

_JS_CLICAR_LINHA = """(i) => {
  const rows = [...document.querySelectorAll('table#TQuery tr')].filter(tr => tr.querySelector('td'));
  const tr = rows[i];
  if (!tr) return false;
  const link = tr.querySelector("a[onclick*='QueryValor']");
  if (!link) return false;
  link.click();
  return true;
}"""


def _ler_grade(popup: Page) -> list[list[str]]:
    return popup.evaluate(_JS_GRADE) or []


def _mesma_linha(a: list[str], b: list[str]) -> bool:
    return [str(c).strip() for c in a] == [str(c).strip() for c in b]


def _linha_confere(popup: Page, indice: int, linhas: list[list[str]]) -> bool:
    """A linha `indice` da grade AGORA e a mesma que foi escolhida?

    A resposta do servidor pode chegar depois da leitura: se a grade mudou,
    o indice aponta para outro cadastro e o clique gravaria o registro errado.
    """
    atuais = _ler_grade(popup)
    if indice >= len(atuais) or indice >= len(linhas):
        return False
    return _mesma_linha(atuais[indice], linhas[indice])


def _popup_filtrar(popup: Page, campo, campo_filtro: str, termo: str) -> list[list[str]]:
    """Filtra o popup de consulta e devolve as linhas da grade (celulas).

    O popup filtra por PREFIXO e os dois filtros (descricao e codigo) sao AND
    no servidor: um filtro velho esquecido impede o resultado novo. Por isso
    os dois sao limpos antes de cada consulta.
    """
    try:
        sem = popup.locator("input[type=checkbox]").first
        if sem.count() and not sem.is_checked():
            sem.evaluate("el => el.click()")
            esperar(popup, 700)
    except Exception:
        pass

    desc_id = campo.filtro_descricao
    cod_id = campo.filtro_codigo
    alvo_id = desc_id if campo_filtro == "descricao" else cod_id
    outro_id = cod_id if campo_filtro == "descricao" else desc_id

    with contextlib.suppress(Exception):
        popup.locator("#" + outro_id).first.fill("")
    try:
        popup.locator("#" + alvo_id).first.fill(termo)
    except Exception as e:
        raise FalhaPopup(f"filtro {alvo_id} nao encontrado ({type(e).__name__})") from e

    with contextlib.suppress(Exception):
        popup.locator("#BPESQUISAR").first.evaluate("el => el.click()")
    esperar(popup, 3500)
    try:
        return _ler_grade(popup)
    except Exception as e:
        raise FalhaPopup(f"grade ilegivel ({type(e).__name__}: {e})") from e


def _popup_esperar_fechar(popup: Page, limite_ms: int = 8000) -> bool:
    """Espera o popup fechar (o link de selecao chama window.close()).

    Nao usa esperar(): wait_for_timeout em pagina ja fechada levanta
    TargetClosedError.
    """
    passos = max(1, limite_ms // 250)
    for _ in range(passos):
        try:
            if popup.is_closed():
                return True
        except Exception:
            return True
        time.sleep(0.25)
    return False


def resolver_lookup_popup(page: Page, campo, termo: str) -> tuple[bool, list[dict]]:
    """Resolve o campo pelo popup de consulta do OpenPort (fonte viva).

    Devolve (resolvido, candidatos). Resolvido e True quando o hidden do
    campo ficou preenchido; nesse caso a lista de candidatos vem vazia.
    """
    try:
        botao = page.locator(campo.seletor_lupa).first
        sem_botao = botao.count() == 0
    except Exception:
        sem_botao = True
    if sem_botao:
        logger.info(f"  {campo.rotulo}: botao lupa nao localizado.")
        return False, []

    try:
        with page.expect_popup(timeout=12000) as pop_info:
            botao.evaluate("el => el.click()")
        popup = pop_info.value
    except Exception as e:
        raise FalhaPopup(f"popup de consulta nao abriu ({type(e).__name__})") from e

    try:
        popup.set_default_timeout(15000)
        with contextlib.suppress(Exception):
            popup.wait_for_load_state("domcontentloaded")
        esperar(popup, 1500)

        candidatos: list[dict] = []
        for campo_filtro, texto in lookup_engine.consultas(termo):
            linhas = _popup_filtrar(popup, campo, campo_filtro, texto)
            if not linhas:
                continue
            idx, cands = lookup_engine.escolher(termo, linhas, campo)
            if cands:
                candidatos = cands
            if idx is None:
                logger.info(
                    f"  {campo.rotulo}: '{texto}' devolveu {len(linhas)} linha(s), "
                    f"sem escolha unica ({len(cands)} candidato(s)).")
                continue
            if not _linha_confere(popup, idx, linhas):
                # A grade mudou entre a leitura e o clique: escolhe de novo na
                # grade atual, sem reenviar a pesquisa.
                linhas = _ler_grade(popup)
                idx, cands = lookup_engine.escolher(termo, linhas, campo)
                if cands:
                    candidatos = cands
                if idx is None or not _linha_confere(popup, idx, linhas):
                    logger.warning(
                        f"  {campo.rotulo}: grade mudou durante a consulta "
                        f"'{texto}' (indice {idx}); nao clica em linha duvidosa.")
                    continue
            try:
                clicou = popup.evaluate(_JS_CLICAR_LINHA, idx)
            except Exception:
                clicou = False
            if not clicou:
                logger.warning(f"  {campo.rotulo}: linha {idx} sem link de selecao.")
                continue
            _popup_esperar_fechar(popup)
            esperar(page, 2000)
            hv = _hidden_valor(page, campo.seletor_hidden)
            if hv:
                logger.info(f"  {campo.rotulo} '{termo}' -> hidden {hv[:20]} (popup).")
                return True, []
            logger.warning(f"  {campo.rotulo} '{termo}': selecao no popup nao preencheu o hidden.")
            return False, candidatos

        logger.warning(f"  {campo.rotulo} '{termo}': nenhum resultado no popup.")
        return False, candidatos
    except FalhaPopup:
        raise
    except Exception as e:
        # Erro de biblioteca (ex. TargetClosedError) nao pode escapar crua: a
        # rodada perderia o registro de erro e o anuncio nao seria retomavel.
        raise FalhaPopup(f"{type(e).__name__}: {e}") from e
    finally:
        with contextlib.suppress(Exception):
            if not popup.is_closed():
                popup.close()


def aceitar_dialogos(page: Page, rotulo=""):
    """Registra handler persistente: loga o texto de todo dialog e aceita (OK).

    Captura confirms ("Deseja confirmar...?"), alertas de erro (ex. 500021)
    e o beforeunload ("Sair do site?") do fechamento.
    """
    def _h(d):
        try:
            logger.info(f"  dialogo [{rotulo}]: {getattr(d, 'message', '')[:300]}")
        except Exception:
            pass
        with contextlib.suppress(Exception):
            d.accept()
    with contextlib.suppress(Exception):
        page.on("dialog", _h)


def screenshot(page: Page, root, nome: str):
    try:
        d = root / "screenshots"
        d.mkdir(exist_ok=True)
        p = d / f"{nome}_{datetime.now():%Y%m%d_%H%M%S}.png"
        page.screenshot(path=str(p))
        logger.info(f"Screenshot: {p.name}")
    except Exception as e:
        logger.warning(f"Screenshot falhou: {e}")
