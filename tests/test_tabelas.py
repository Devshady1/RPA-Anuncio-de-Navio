import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import tabelas


class TestTabelasAfretador(unittest.TestCase):
    def test_afretador_resolve_nome(self):
        self.assertEqual(tabelas.resolver("afretador", "TAMAR SHIP MANAGEMENT")[0],
                         "00000000000005")

    def test_afretador_resolve_codigo(self):
        self.assertEqual(tabelas.resolver("afretador", "00000000000005")[0],
                         "00000000000005")


if __name__ == "__main__":
    unittest.main()
