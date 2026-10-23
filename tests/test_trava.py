import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import trava


class TestTrava(unittest.TestCase):
    def test_segunda_instancia_nao_entra(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "servico.lock"
            self.assertTrue(trava.adquirir(p))
            self.assertFalse(trava.adquirir(p))
            trava.liberar(p)
            self.assertTrue(trava.adquirir(p))

    def test_lock_velho_e_roubado(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "servico.lock"
            p.write_text("123 2000-01-01T00:00:00")
            self.assertTrue(trava.adquirir(p, agora=time.time()))


if __name__ == "__main__":
    unittest.main()
