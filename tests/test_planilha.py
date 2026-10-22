import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from openpyxl import Workbook

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


def _ficha_com(rotulo: str, valor: str) -> dict:
    """Monta uma ficha .xlsx temporaria e devolve os campos lidos dela."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Anúncio"
    ws.append(["Campo", "", "Preencher", ""])
    for r, v in (
        ("nome do navio", "NAVIO TESTE"),
        ("imo", "9553256"),
        ("eta data", "16/10/2026"),
        ("carga predominante (mercadoria)", "26040000"),
        (rotulo, valor),
    ):
        ws.append([r, "", v, ""])
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        wb.save(tmp.name)
        return planilha.ler_planilha(tmp.name)
    finally:
        os.unlink(tmp.name)


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


class TestLookupsPreservamTexto(unittest.TestCase):
    def test_nome_desconhecido_nao_derruba_a_ficha(self):
        # 'ZZZ EMPRESA QUE NAO EXISTE' nao esta no CSV local, mas pode existir
        # no OpenPort: a decisao final e do popup, nao da copia local.
        campos = _ficha_com("armador (nome ou código)", "ZZZ EMPRESA QUE NAO EXISTE")
        self.assertEqual(campos["armador"], "ZZZ EMPRESA QUE NAO EXISTE")
        self.assertEqual(campos.get("armador_codigo", ""), "")

    def test_nome_conhecido_guarda_o_codigo_como_fallback(self):
        campos = _ficha_com("armador (nome ou código)", "MARINAV")
        self.assertEqual(campos["armador"], "MARINAV")
        self.assertEqual(campos["armador_codigo"], "30010")

    def test_texto_com_codigo_e_nome_preserva_o_texto(self):
        campos = _ficha_com("agência (nome ou código)", "30010 - MARINAV")
        self.assertEqual(campos["agencia"], "30010 - MARINAV")
        self.assertEqual(campos["agencia_codigo"], "30010")

    def test_carga_que_nao_existe_nao_derruba_a_ficha(self):
        campos = _ficha_com("carga predominante (mercadoria)", "ZZZ CARGA QUE NAO EXISTE")
        self.assertEqual(campos["carga"], "ZZZ CARGA QUE NAO EXISTE")
        self.assertEqual(campos.get("carga_codigo", ""), "")

    def test_berco_preserva_o_texto(self):
        campos = _ficha_com("berço preferência", "BERÇO 101")
        self.assertEqual(campos["berco"], "BERÇO 101")


if __name__ == "__main__":
    unittest.main()
