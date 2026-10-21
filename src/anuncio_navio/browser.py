import contextlib
import logging
import re
from datetime import datetime

from playwright.sync_api import Page, BrowserContext

logger = logging.getLogger("anuncio.browser")

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
