"""Fluxo completo de anuncio no QAS partindo de NOMES (nada e gravado).

Prova o que a Task 3 entregou: a ficha escrita com nome (nao com codigo)
resolve os 8 lookups pelo popup do OpenPort e chega ao fim do formulario.

O teste NUNCA grava: o botao Gravar/Verificar/Confirmar e registrado, nao
clicado, e a verificacao na 2001 e substituida por "nao encontrado" (nao ha
o que procurar, nada foi gravado).
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import anuncio, browser, fila_json, lookup_engine, main, verificar
from anuncio_navio.config import Config, URL_QAS
from anuncio_navio.exceptions import AnuncioError, VerificacaoError

# Termos VALIDADOS no QAS vivo (tests/test_lookup_qas.py): cada um com o
# codigo que o popup devolve.
ESPERADO = {
    "porto_ant": "BRIOS",
    "porto_prox": "BRSSZ",
    "armador": "60700",
    "afretador": "60210",
    "agencia": "30010",
    "berco": "101",
    "operador": "30002",
    "carga": "02061000",
}

FICHA_COM_NOMES = {
    "nome_navio": "VOYAGER",
    "imo": "9553256",
    "viagem": "009999",          # par imo/viagem novo: nao cai na anti-duplicidade
    "agencia": "MARINAV",
    "armador": "AMELIA NAVIGATION",
    "afretador": "AEC SHIPPING",
    "operador": "INTERMARIT",
    "porto_ant": "Ilhéus",
    "porto_prox": "Santos",
    "berco": "BERÇO 101",
    "carga": "MIUDEZAS COMESTIVEIS",
    "eta": "20/11/2026 07:30",
    "etb": "21/11/2026 08:00",
    "etc": "22/11/2026 12:00",
    "ets": "22/11/2026 19:00",
    "qtd": "1000",
    "tons": "1000",
    "calado": {"chegada_proa": "8.30", "chegada_popa": "8.30",
               "saida_proa": "8.30", "saida_popa": "8.30"},
}


@unittest.skipUnless(os.getenv("RUN_QAS_TESTS") == "1",
                     "definir RUN_QAS_TESTS=1 para rodar contra o QAS")
class TestAnuncioCompletoNoQas(unittest.TestCase):
    def setUp(self):
        cfg = Config.from_env(url_override=URL_QAS)
        self.assertIn("/qas/", cfg.url, "teste de QAS rodando fora do QAS")
        self.assertNotIn("PERMITIR_PROD", os.environ,
                         "PERMITIR_PROD setado: teste de QAS nao pode ir a PROD")
        self.cfg = cfg

        # 1) nada destrutivo e clicado: Gravar/Verificar/Confirmar ficam
        # registrados; os demais botoes (o "Entrar" do login, por exemplo)
        # funcionam normalmente.
        self.acionados = []
        original_acionar = browser.acionar
        destrutivos = {cfg.css["btn_gravar"], cfg.css["btn_verificar"]}
        if cfg.css.get("btn_confirmar"):
            destrutivos.add(cfg.css["btn_confirmar"])

        def spy_acionar(page, css, *args, **kwargs):
            self.acionados.append(css)
            if css in destrutivos:
                return True
            return original_acionar(page, css, *args, **kwargs)

        browser.acionar = spy_acionar
        self.addCleanup(setattr, browser, "acionar", original_acionar)

        # 2) a verificacao na 2001 vira "nao encontrado": nada foi gravado
        original_confirmado = verificar.confirmado_na_2001
        verificar.confirmado_na_2001 = lambda *a, **k: False
        self.addCleanup(setattr, verificar, "confirmado_na_2001", original_confirmado)

    def test_ficha_com_nomes_preenche_os_lookups_e_chega_ao_fim(self):
        vistos = {}
        original_criar = anuncio.criar_anuncio

        def spy_criar(page, config, dados):
            duv = original_criar(page, config, dados)
            for campo in lookup_engine.CAMPOS:
                vistos[campo.chave] = {
                    "hidden": page.locator(campo.seletor_hidden).first.input_value().strip(),
                    "visivel": page.locator(campo.seletor_visivel).first.input_value().strip(),
                }
            return duv

        anuncio.criar_anuncio = spy_criar
        self.addCleanup(setattr, anuncio, "criar_anuncio", original_criar)

        dados = fila_json.normalizar(FICHA_COM_NOMES)
        with self.assertRaises(VerificacaoError) as ctx:
            main.executar_um(self.cfg, dados)

        # Nao pode ser LookupError: o anuncio chegou ate o fim do formulario.
        self.assertNotIsInstance(ctx.exception, LookupError)
        self.assertIsInstance(ctx.exception, AnuncioError)

        # Os 8 lookups ficaram preenchidos, com o codigo que o popup devolve.
        for chave, esperado in ESPERADO.items():
            self.assertIn(chave, vistos, f"{chave} nem foi processado")
            self.assertTrue(vistos[chave]["hidden"], f"{chave}: hidden vazio")
            self.assertEqual(vistos[chave]["visivel"], esperado,
                             f"{chave}: visivel={vistos[chave]['visivel']!r}")

        # O Gravar foi alcancado (registrado), mas nao clicado de verdade.
        self.assertIn(self.cfg.css["btn_gravar"], self.acionados)


if __name__ == "__main__":
    unittest.main()
