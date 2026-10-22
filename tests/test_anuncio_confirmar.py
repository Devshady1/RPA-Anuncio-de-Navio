import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import anuncio
from anuncio_navio.config import Config

DADOS = {
    "imo": "9553256", "viagem": "000008", "tipo_viagem": "1", "tipo_operacao": "1",
    "sentido": "1", "natureza": "1",
    "calado_cheg_proa": "8.30", "calado_cheg_popa": "8.30",
    "calado_sai_proa": "8.30", "calado_sai_popa": "8.30",
    "qtd": "1000", "tons": "1000",
    "porto_ant": "Ilhéus", "porto_prox": "Santos", "armador": "AMELIA NAVIGATION",
    "afretador": "AEC SHIPPING", "agencia": "MARINAV", "berco": "BERÇO 101",
    "operador": "INTERMARIT", "carga": "MIUDEZAS COMESTIVEIS",
}


def _cfg():
    return SimpleNamespace(css=Config.from_env(dotenv_path=None).css, project_root=ROOT)


def _pagina(cfg):
    page = mock.MagicMock()
    valores = {cfg.css["navio_nome"]: "VOYAGER", cfg.css["duv"]: "000008"}

    def _locator(sel):
        loc = mock.MagicMock()
        loc.first.input_value.return_value = valores.get(sel, "")
        return loc

    page.locator.side_effect = _locator
    return page


class TestSequenciaAposVerificar(unittest.TestCase):
    """Gravar -> Verificar -> (Confirmar). O regravar apos Verificar e sempre
    recusado pelo OpenPort (200301, status Elaborado), entao nao pode existir."""

    def _rodar(self, confirmar: bool):
        cfg = _cfg()
        cliques = []
        with mock.patch.object(anuncio.browser, "acionar",
                               side_effect=lambda p, sel: cliques.append(sel)), \
             mock.patch.object(anuncio.browser, "preencher"), \
             mock.patch.object(anuncio.browser, "selecionar"), \
             mock.patch.object(anuncio.browser, "esperar"), \
             mock.patch.object(anuncio.browser, "aceitar_dialogos"), \
             mock.patch.object(anuncio.browser, "screenshot"), \
             mock.patch.object(anuncio.browser, "resolver_lookup_popup",
                               return_value=(True, [{"codigo": "1", "descricao": "X"}])), \
             mock.patch.dict(os.environ, {"CONFIRMAR_ANUNCIO": "1" if confirmar else "0"}):
            duv = anuncio.criar_anuncio(_pagina(cfg), cfg, dict(DADOS))
        return cliques, duv

    def test_confirmar_vai_direto_do_verificar_para_o_confirmar(self):
        cliques, duv = self._rodar(confirmar=True)
        css = _cfg().css
        self.assertEqual(cliques, [css["btn_gravar"], css["btn_verificar"],
                                   css["btn_confirmar"]])
        self.assertEqual(duv, "000008")

    def test_sem_confirmar_para_no_verificar(self):
        cliques, _ = self._rodar(confirmar=False)
        css = _cfg().css
        self.assertEqual(cliques, [css["btn_gravar"], css["btn_verificar"]])


if __name__ == "__main__":
    unittest.main()
