import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import planilha

BASE = {
    "nome_navio": "NAVIO TESTE",
    "imo": "9553256",
    "agencia": "30010",
    "armador": "100626",
    "operador": "30002",
    "porto_ant": "BRMCZ",
    "porto_prox": "ESVIT",
    "carga": "26040000",
    "qtd": "11200",
    "loa": "179.93",
    "eta_data": "16/10/2026",
    "eta_hora": "11:00",
    "etb_data": "19/10/2026",
    "etb_hora": "08:00",
    "etc_data": "20/10/2026",
    "etc_hora": "12:00",
    "ets_data": "20/10/2026",
    "ets_hora": "19:00",
    "tipo_viagem": "1",
    "tipo_operacao": "1",
    "sentido": "1",
    "natureza": "1",
    "calado_cheg_proa": "9",
    "calado_cheg_popa": "5",
    "calado_sai_proa": "10",
    "calado_sai_popa": "6",
}


def _erros(**over):
    c = dict(BASE)
    c.update(over)
    return planilha.validar_campos(c)


class TestCalado(unittest.TestCase):
    def test_base_sem_erros(self):
        self.assertEqual(_erros(), [])

    def test_teto_do_porto_16m_passa(self):
        self.assertEqual(_erros(calado_cheg_proa="16"), [])

    def test_acima_do_teto_do_porto_reprovado(self):
        erros = _erros(calado_sai_proa="16.5")
        self.assertTrue(any("calado_sai_proa" in e for e in erros), erros)

    def test_calado_zero_ou_negativo_reprovado(self):
        self.assertTrue(any("calado_cheg_proa" in e for e in _erros(calado_cheg_proa="0")))
        self.assertTrue(any("calado_sai_popa" in e for e in _erros(calado_sai_popa="-1")))

    def test_calado_nao_numerico_reprovado(self):
        self.assertTrue(any("numerico" in e for e in _erros(calado_cheg_proa="dez")))


if __name__ == "__main__":
    unittest.main()
