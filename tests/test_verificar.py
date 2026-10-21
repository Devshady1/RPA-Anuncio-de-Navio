import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import verificar as V
from anuncio_navio.exceptions import VerificacaoError


CABECALHOS = ["Progr.", "IMO", "Navio", "Viagem", "Tipo", "ETA", "Status", "Nº da DUV"]
LINHA_OK = ["1773", "9553256", "VOYAGER", "000003", "LONGO CURSO", "05/10/2026 07:30", "Anunciado", ""]


class TestVerificar(unittest.TestCase):
    def test_data_filtro(self):
        self.assertEqual(V._data_filtro("05/10/2026 07:30"), "05/10/2026")
        self.assertEqual(V._data_filtro("2026-10-05"), "05/10/2026")
        with self.assertRaises(VerificacaoError):
            V._data_filtro("sem-data")

    def test_status_esperado(self):
        anterior = os.environ.get("STATUS_2001_ESPERADO")
        os.environ.pop("STATUS_2001_ESPERADO", None)
        try:
            self.assertEqual(V._valores_status_esperados(None), ["2,00"])
            self.assertEqual(V._valores_status_esperados("Anúncio Completo"), ["8,00"])
            with self.assertRaises(VerificacaoError):
                V._valores_status_esperados("Status Inexistente")
        finally:
            if anterior is not None:
                os.environ["STATUS_2001_ESPERADO"] = anterior

    def test_linha_e_cabecalho(self):
        mapa = V._mapa_colunas(CABECALHOS)
        self.assertEqual((mapa["progr"], mapa["imo"], mapa["viagem"], mapa["eta"], mapa["status"], mapa["duv"]), (0, 1, 3, 5, 6, 7))
        self.assertTrue(V._linha_confere(LINHA_OK, mapa, "9553256", "05/10/2026", ["2,00"], "000003", "000003"))
        errada = list(LINHA_OK)
        errada[6] = "Despachado"
        self.assertFalse(V._linha_confere(errada, mapa, "9553256", "05/10/2026", ["2,00"], "000003", "000003"))
        self.assertTrue(V._cabecalho_confere("1773 - VOYAGER - IMO 9553256 - Anunciado", "1773", "9553256", "Anunciado"))
        self.assertFalse(V._cabecalho_confere("1773 - VOYAGER - IMO 9553256 - Despachado", "1773", "9553256", "Anunciado"))


if __name__ == "__main__":
    unittest.main()
