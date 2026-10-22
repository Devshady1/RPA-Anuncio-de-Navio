import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import browser


def _popup(grade):
    return SimpleNamespace(evaluate=lambda *a, **k: grade)


class TestLinhaConfere(unittest.TestCase):
    """O indice escolhido so vale se a grade ainda for a mesma no clique."""

    def test_grade_igual_confere(self):
        grade = [["", "30010", "MARINAV"], ["", "30002", "INTERMARIT"]]
        self.assertTrue(browser._linha_confere(_popup(grade), 0, grade))

    def test_grade_reordenada_nao_confere(self):
        # Resposta lenta do servidor reordenou a grade: clicar no indice 0
        # gravaria INTERMARIT no lugar de MARINAV.
        escolhida = [["", "30010", "MARINAV"], ["", "30002", "INTERMARIT"]]
        agora = [["", "30002", "INTERMARIT"], ["", "30010", "MARINAV"]]
        self.assertFalse(browser._linha_confere(_popup(agora), 0, escolhida))

    def test_linha_sumiu_nao_confere(self):
        escolhida = [["", "30010", "MARINAV"], ["", "30002", "INTERMARIT"]]
        agora = [["", "30002", "INTERMARIT"]]
        self.assertFalse(browser._linha_confere(_popup(agora), 1, escolhida))
        self.assertFalse(browser._linha_confere(_popup([]), 0, escolhida))

    def test_espaco_em_volta_da_celula_nao_importa(self):
        escolhida = [[" ", "30010", "MARINAV "]]
        agora = [["", " 30010", "MARINAV"]]
        self.assertTrue(browser._linha_confere(_popup(agora), 0, escolhida))


if __name__ == "__main__":
    unittest.main()
