import sys
import multiprocessing
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import trava


def _tentar_lock_em_processo(path, resultado):
    adquirido = trava.adquirir(Path(path))
    resultado.put(adquirido)
    if adquirido:
        trava.liberar(Path(path))


class TestTrava(unittest.TestCase):
    def test_segunda_instancia_nao_entra(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "servico.lock"
            self.assertTrue(trava.adquirir(p))
            self.assertFalse(trava.adquirir(p))
            trava.liberar(p)
            self.assertTrue(trava.adquirir(p))
            trava.liberar(p)

    def test_arquivo_de_lock_existente_nao_bloqueia_instancia(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "servico.lock"
            p.write_text("123 2000-01-01T00:00:00")
            self.assertTrue(trava.adquirir(p))
            trava.liberar(p)

    def test_lock_exclusivo_entre_processos(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "servico.lock"
            self.assertTrue(trava.adquirir(p))
            contexto = multiprocessing.get_context("spawn")
            resultado = contexto.Queue()
            processo = contexto.Process(target=_tentar_lock_em_processo, args=(str(p), resultado))
            processo.start()
            processo.join(timeout=10)
            self.assertFalse(processo.is_alive(), "processo de teste nao terminou")
            self.assertEqual(processo.exitcode, 0)
            self.assertFalse(resultado.get(timeout=2))
            trava.liberar(p)


if __name__ == "__main__":
    unittest.main()
