import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import main, trava
from anuncio_navio.exceptions import AnuncioEmAndamentoError


class TestExecucaoSequencial(unittest.TestCase):
    def test_segundo_anuncio_e_bloqueado_enquanto_primeiro_executa(self):
        with TemporaryDirectory() as temp:
            cfg = SimpleNamespace(project_root=Path(temp))
            iniciou = threading.Event()
            concluir = threading.Event()
            resultados = []

            def executar_lento(_cfg, _dados):
                iniciou.set()
                if not concluir.wait(timeout=5):
                    raise TimeoutError("o teste nao liberou a primeira execucao")
                return "duv-1"

            with patch.object(main, "_executar_um", side_effect=executar_lento):
                thread = threading.Thread(
                    target=lambda: resultados.append(main.executar_um(cfg, {}))
                )
                thread.start()
                self.assertTrue(iniciou.wait(timeout=5))
                try:
                    with self.assertRaises(AnuncioEmAndamentoError):
                        main.executar_um(cfg, {})
                finally:
                    concluir.set()
                    thread.join(timeout=5)

            self.assertFalse(thread.is_alive(), "a primeira execucao nao terminou")
            self.assertEqual(resultados, ["duv-1"])
            lock = Path(temp) / "logs" / "anuncio.lock"
            self.assertTrue(trava.adquirir(lock))
            trava.liberar(lock)


if __name__ == "__main__":
    unittest.main()
