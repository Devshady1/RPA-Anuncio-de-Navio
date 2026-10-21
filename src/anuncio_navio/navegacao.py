import contextlib
import logging

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PWTimeout

from . import browser
from .exceptions import LoginError, VerificacaoError
from .retry import com_retry

logger = logging.getLogger("anuncio.navegacao")


@com_retry(tentativas=3, backoff_base=2.0, excecoes=(LoginError, Exception))
def login(page: Page, config) -> None:
    logger.info(f"Acessando {config.url}")
    page.goto(config.url, wait_until="domcontentloaded")
    browser.esperar(page, 2500)
    browser.maximizar(page)
    browser.bloquear(page)
    browser.preencher(page, config.css["login"], config.login)
    browser.preencher(page, config.css["senha"], config.senha)
    browser.acionar(page, config.css["entrar"])
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle")
    browser.esperar(page, 2500)
    try:
        page.locator("input#User").wait_for(state="hidden", timeout=8000)
        logger.info("Login OK.")
    except PWTimeout:
        browser.screenshot(page, config.project_root, "login_falhou")
        raise LoginError("Login nao concluiu. Confira credencial QAS.")


def abrir_tela_2003(page: Page, config) -> None:
    logger.info("Abrindo tela 2003...")
    browser.preencher(page, config.css["menu_acesso"], "2003")
    browser.esperar(page, 500)
    page.keyboard.press("Enter")
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle")
    browser.esperar(page, 2500)
    browser.bloquear(page)
    browser.maximizar(page)


def abrir_tela_2001(page: Page, config) -> None:
    logger.info("Abrindo tela 2001...")
    browser.preencher(page, config.css["menu_acesso"], "2001")
    browser.esperar(page, 500)
    page.keyboard.press("Enter")
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle")
    browser.esperar(page, 2500)
    browser.bloquear(page)
    browser.maximizar(page)
    try:
        page.locator(config.css["btn_filtrar_2001"]).wait_for(state="visible", timeout=15000)
        logger.info("Tela 2001 aberta.")
    except PWTimeout:
        browser.screenshot(page, config.project_root, "tela_2001_nao_abriu")
        raise VerificacaoError("Tela 2001 nao abriu. Verificacao cancelada antes de marcar OK.")


def novo_registro(page: Page, config) -> None:
    logger.info("Clicando Novo (lista #INSERIR)...")
    browser.acionar(page, config.css.get("btn_novo_lista", "button#INSERIR"))
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle")
    browser.esperar(page, 2000)
