import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import browser, lookup_engine, navegacao
from anuncio_navio.config import Config, URL_QAS


@unittest.skipUnless(os.getenv("RUN_QAS_TESTS") == "1",
                     "definir RUN_QAS_TESTS=1 para rodar contra o QAS")
class TestLookupNoQas(unittest.TestCase):
    CASOS = [
        ("agencia", "MARINAV", "30010"),
        ("armador", "AMELIA NAVIGATION", "60700"),
        # 0052025 (AFRICAN TOUCAN SHIPPING CO) e ARMADOR, nao afretador: a
        # lista de afretadores do QAS nao traz esse cadastro.
        ("afretador", "AEC SHIPPING", "60210"),
        ("operador", "INTERMARIT", "30002"),
        ("berco", "BERÇO 101", "101"),
        ("porto_ant", "Ilhéus", "BRIOS"),
        ("porto_prox", "Santos", "BRSSZ"),
        ("carga", "MIUDEZAS COMESTIVEIS", "02061000"),
    ]

    # A ficha antiga vem com CODIGO. O popup tem de achar por codigo tambem:
    # o de porto e alfanumerico ('BRIOS'), o de empresa e numerico.
    CASOS_CODIGO = [
        ("porto_ant", "BRIOS", "BRIOS"),
        ("agencia", "30010", "30010"),
        ("agencia", "30010 - MARINAV", "30010"),
    ]

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.bw = cls.pw.chromium.launch(headless=True, slow_mo=0)
        cls.ctx = cls.bw.new_context(no_viewport=True)
        cls.ctx.set_default_timeout(20000)
        browser.ao_nova_pagina(cls.ctx)
        cls.page = cls.ctx.new_page()
        cfg = Config.from_env(url_override=URL_QAS)
        assert cfg.ambiente == "QAS", cfg.url
        cls.cfg = cfg
        navegacao.login(cls.page, cfg)
        navegacao.abrir_tela_2003(cls.page, cfg)
        navegacao.novo_registro(cls.page, cfg)

    @classmethod
    def tearDownClass(cls):
        for obj in ("ctx", "bw"):
            try:
                getattr(cls, obj).close()
            except Exception:
                pass
        try:
            cls.pw.stop()
        except Exception:
            pass

    def test_resolve_por_nome(self):
        for chave, termo, codigo_esperado in self.CASOS:
            campo = next(c for c in lookup_engine.CAMPOS if c.chave == chave)
            ok, cands = browser.resolver_lookup_popup(self.page, campo, termo)
            self.assertTrue(ok, f"{chave}: nao resolveu '{termo}' (candidatos={cands})")
            visivel = self.page.locator(campo.seletor_visivel).first.input_value().strip()
            self.assertEqual(visivel, codigo_esperado, f"{chave}: visivel='{visivel}'")
            hidden = self.page.locator(campo.seletor_hidden).first.input_value().strip()
            self.assertTrue(hidden, f"{chave}: hidden vazio")

    def test_resolve_por_codigo(self):
        for chave, termo, codigo_esperado in self.CASOS_CODIGO:
            campo = next(c for c in lookup_engine.CAMPOS if c.chave == chave)
            ok, cands = browser.resolver_lookup_popup(self.page, campo, termo)
            self.assertTrue(ok, f"{chave}: nao resolveu '{termo}' (candidatos={cands})")
            visivel = self.page.locator(campo.seletor_visivel).first.input_value().strip()
            self.assertEqual(visivel, codigo_esperado, f"{chave}: visivel='{visivel}'")
            hidden = self.page.locator(campo.seletor_hidden).first.input_value().strip()
            self.assertTrue(hidden, f"{chave}: hidden vazio")

    def test_filtro_traz_a_lista_inteira_sem_paginacao(self):
        # 'sem paginacao' desmarcada devolve a pagina 1; o prefixo 'A' no popup
        # de portos tem mais de mil linhas. Se a lista vier truncada, o indice
        # escolhido pela engine aponta para a linha errada.
        campo = next(c for c in lookup_engine.CAMPOS if c.chave == "porto_ant")
        with self.page.expect_popup(timeout=12000) as pi:
            self.page.locator(campo.seletor_lupa).first.evaluate("el => el.click()")
        popup = pi.value
        try:
            popup.set_default_timeout(15000)
            popup.wait_for_load_state("domcontentloaded")
            browser.esperar(popup, 2000)
            linhas = browser._popup_filtrar(popup, campo, "descricao", "A")
            self.assertGreater(len(linhas), 100, f"lista truncada: {len(linhas)}")
        finally:
            popup.close()


if __name__ == "__main__":
    unittest.main()
