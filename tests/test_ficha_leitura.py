import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import openpyxl

from anuncio_navio import ficha

MODELO = Path(__file__).resolve().parents[1] / "src" / "anuncio_navio" / "recursos" / "ficha_modelo.xlsx"


class TestLeitura(unittest.TestCase):
    def _ficha_com(self, root, valores):
        p = root / "ficha" / "ficha_anuncio_navio.xlsx"
        shutil.copyfile(MODELO, p)
        wb = openpyxl.load_workbook(p)
        for cel, v in valores.items():
            wb["Anúncio"][cel] = v
        wb.save(p)
        return p

    def test_faltando_campos_vira_mensagem(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            (root / "ficha").mkdir()
            self._ficha_com(root, {"C6": "VOYAGER"})
            campos, pendencias = ficha.ler(root)
            msg = ficha.mensagem_invalida(pendencias)
        self.assertEqual(campos["nome_navio"], "VOYAGER")
        self.assertEqual(campos["imo"], "")
        self.assertIn("IMO", pendencias)
        self.assertTrue(msg.startswith("NÃO FOI ENVIADO —"))
        self.assertIn("Corrija e salve de novo.", msg)

    def test_ficha_valida_nao_tem_pendencias(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            (root / "ficha").mkdir()
            self._ficha_com(root, self.CAMPOS_OK)
            campos, pendencias = ficha.ler(root)
        self.assertEqual(pendencias, [])
        self.assertEqual(campos["porto_prox"], "Santos")

    CAMPOS_OK = {
        "C6": "VOYAGER", "C7": "9553256", "C8": "190", "C11": "Ilheus",
        "C12": "28/11/2026", "D12": "07:30", "C13": "29/11/2026", "D13": "08:00",
        "C14": "30/11/2026", "D14": "12:00", "C15": "30/11/2026", "D15": "19:00",
        "C16": "Santos", "C17": "BERÇO 101", "C19": "MIUDEZAS COMESTIVEIS",
        "C20": "1000", "C21": "1000", "C22": "8,30", "D22": "8,30",
        "C23": "8,30", "D23": "8,30", "C25": "MARINAV", "C26": "AMELIA",
        "C27": "INTERMARIT", "C28": "AEC SHIPPING",
    }


if __name__ == "__main__":
    unittest.main()
