import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import monitor_fila
from anuncio_navio import trava


class TestModoServico(unittest.TestCase):
    def test_uma_vez_chama_processar_uma_vez_e_devolve_0(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {"ANUNCIO_ROOT": t}):
            chamadas = []

            def processar(root, cfg):
                chamadas.append((root, cfg))
                return SimpleNamespace(estado="sem_ficha")

            rc = monitor_fila.modo_servico(0.01, True, processar_fn=processar)

            self.assertEqual(rc, 0)
            self.assertEqual(len(chamadas), 1)
            self.assertEqual(chamadas[0][0], Path(t).resolve())
            self.assertFalse((Path(t) / "logs" / "servico.lock").exists())

    def test_trava_ocupada_nao_chama_processar_e_devolve_0(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {"ANUNCIO_ROOT": t}):
            root = Path(t)
            (root / "logs").mkdir()
            lock = root / "logs" / "servico.lock"
            self.assertTrue(trava.adquirir(lock))
            chamadas = []

            rc = monitor_fila.modo_servico(
                0.01, True, processar_fn=lambda r, c: chamadas.append(1))

            self.assertEqual(rc, 0)
            self.assertEqual(chamadas, [])
            self.assertTrue(lock.exists())

    def test_ocupada_notifica_uma_vez_por_episodio(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {"ANUNCIO_ROOT": t}):
            root = Path(t)
            (root / "ficha").mkdir()
            (root / "ficha" / "ficha_anuncio_navio.xlsx").write_bytes(b"x")
            avisos = []
            paradas = []

            def dormir(_):
                paradas.append(1)
                if len(paradas) == 2:
                    raise KeyboardInterrupt

            with patch("monitor_fila.notificar.notificar",
                       side_effect=lambda ti, tx: avisos.append((ti, tx))):
                rc = monitor_fila.modo_servico(
                    0.01, False,
                    processar_fn=lambda r, c: SimpleNamespace(estado="ocupada"),
                    dormir=dormir)

            self.assertEqual(rc, 0)
            self.assertEqual(
                avisos, [("Anúncio", "Feche a planilha para o robô processar.")])
            self.assertFalse((root / "logs" / "servico.lock").exists())


if __name__ == "__main__":
    unittest.main()
