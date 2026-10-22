import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import anuncio, browser
from anuncio_navio.config import Config

LOOKUPS = {
    "porto_ant": "Ilhéus", "porto_prox": "Santos",
    "armador": "MARINAV", "afretador": "AEC SHIPPING",
    "agencia": "MARINAV", "berco": "BERÇO 101",
    "operador": "INTERMARIT", "carga": "MIUDEZAS COMESTIVEIS",
}


def _dados(**extra):
    d = {"imo": "9553256", "viagem": "000009", "tipo_viagem": "1",
         "tipo_operacao": "1", "sentido": "1", "natureza": "1",
         "calado_cheg_proa": "8.30", "calado_cheg_popa": "8.30",
         "calado_sai_proa": "8.30", "calado_sai_popa": "8.30",
         "qtd": "1000", "tons": "1000"}
    d.update(LOOKUPS)
    d.update(extra)
    return d


def _cfg():
    return SimpleNamespace(css=Config.from_env(dotenv_path=None).css, project_root=ROOT)


def _so(chave, resposta):
    """Resposta do popup so para um campo; os demais resolvem normalmente."""
    def _r(page, campo, termo):
        return resposta if campo.chave == chave else (True, [])
    return _r


def _pagina(cfg):
    page = mock.MagicMock()
    valores = {cfg.css["navio_nome"]: "VOYAGER", cfg.css["duv"]: "000009"}

    def _locator(sel):
        loc = mock.MagicMock()
        loc.first.input_value.return_value = valores.get(sel, "")
        return loc

    page.locator.side_effect = _locator
    return page


class TestBloco3(unittest.TestCase):
    """Popup e a fonte; CSV so como fallback; nada de Gravar sem resolver."""

    def _rodar(self, resolver, dados=None):
        cfg = _cfg()
        cliques = []
        preencher_lookup = mock.MagicMock(return_value=True)
        with mock.patch.object(anuncio.browser, "acionar",
                               side_effect=lambda p, sel: cliques.append(sel)), \
             mock.patch.object(anuncio.browser, "preencher"), \
             mock.patch.object(anuncio.browser, "selecionar"), \
             mock.patch.object(anuncio.browser, "esperar"), \
             mock.patch.object(anuncio.browser, "aceitar_dialogos"), \
             mock.patch.object(anuncio.browser, "screenshot"), \
             mock.patch.object(anuncio.browser, "resolver_lookup_popup",
                               side_effect=resolver), \
             mock.patch.object(anuncio.browser, "preencher_lookup",
                               preencher_lookup), \
             mock.patch.dict(os.environ, {"CONFIRMAR_ANUNCIO": "0"}):
            try:
                anuncio.criar_anuncio(_pagina(cfg), cfg, dados or _dados())
            except anuncio.LookupError as e:
                return "lookup", str(e), cliques, preencher_lookup
        return "ok", "", cliques, preencher_lookup

    def test_popup_resolve_nao_usa_o_csv(self):
        estado, _, cliques, preencher_lookup = self._rodar(
            lambda page, campo, termo: (True, []),
            _dados(armador_codigo="30010"))
        self.assertEqual(estado, "ok")
        preencher_lookup.assert_not_called()
        self.assertIn(_cfg().css["btn_gravar"], cliques)

    def test_popup_sem_resultado_usa_o_codigo_do_csv(self):
        estado, _, cliques, preencher_lookup = self._rodar(
            _so("armador", (False, [])), _dados(armador_codigo="30010"))
        self.assertEqual(estado, "ok")
        preencher_lookup.assert_called_once()
        self.assertIn(_cfg().css["btn_gravar"], cliques)

    def test_ambiguidade_barra_antes_do_gravar(self):
        ambiguos = [{"codigo": "60700", "descricao": "AMELIA NAVIGATION", "score": 0.8},
                    {"codigo": "60162", "descricao": "Amelia ship", "score": 0.8}]
        estado, msg, cliques, preencher_lookup = self._rodar(
            _so("armador", (False, ambiguos)),
            _dados(armador="AMELIA", armador_codigo="60700"))
        self.assertEqual(estado, "lookup")
        self.assertIn("AMELIA NAVIGATION", msg)
        preencher_lookup.assert_not_called()
        self.assertNotIn(_cfg().css["btn_gravar"], cliques)

    def test_falha_tecnica_do_popup_barra_sem_usar_o_csv(self):
        def resolver(page, campo, termo):
            if campo.chave == "armador":
                raise browser.FalhaPopup("filtro sqlCOD_EMPRESA nao encontrado")
            return True, []

        estado, msg, cliques, preencher_lookup = self._rodar(
            resolver, _dados(armador_codigo="30010"))
        self.assertEqual(estado, "lookup")
        self.assertIn("falha tecnica", msg)
        preencher_lookup.assert_not_called()
        self.assertNotIn(_cfg().css["btn_gravar"], cliques)


if __name__ == "__main__":
    unittest.main()
