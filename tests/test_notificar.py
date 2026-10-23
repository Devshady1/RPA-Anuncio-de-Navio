import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio.notificar import notificar


class TestNotificar(unittest.TestCase):
    def test_darwin_chama_osascript(self):
        chamadas = []
        ok = notificar("Anúncio de Navio", "Anúncio 9553256 gravado",
                       runner=lambda cmd, **kw: chamadas.append(cmd), sistema="darwin")
        self.assertTrue(ok)
        self.assertEqual(chamadas[0][:2], ["osascript", "-e"])
        self.assertIn("display notification", chamadas[0][2])
        self.assertIn("Anúncio 9553256 gravado", chamadas[0][2])
        self.assertIn("Anúncio de Navio", chamadas[0][2])

    def test_fora_do_mac_nao_chama_nada(self):
        chamadas = []
        ok = notificar("t", "x", runner=lambda cmd, **kw: chamadas.append(cmd), sistema="win32")
        self.assertFalse(ok)
        self.assertEqual(chamadas, [])


if __name__ == "__main__":
    unittest.main()
