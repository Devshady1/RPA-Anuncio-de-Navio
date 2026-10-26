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
        with TemporaryDirectory() as t, patch.dict(os.environ, {
            "ANUNCIO_ROOT": t,
            "OPENPORT_URL": "https://ilheus.codeba.gov.br/qas/openportcodeba/",
        }):
            chamadas = []

            def processar(root, cfg):
                chamadas.append((root, cfg))
                return SimpleNamespace(estado="sem_ficha")

            rc = monitor_fila.modo_servico(0.01, True, processar_fn=processar)

            self.assertEqual(rc, 0)
            self.assertEqual(len(chamadas), 1)
            self.assertEqual(chamadas[0][0], Path(t).resolve())
            self.assertTrue((Path(t) / "logs" / "servico.lock").exists())
            self.assertTrue(trava.adquirir(Path(t) / "logs" / "servico.lock"))
            trava.liberar(Path(t) / "logs" / "servico.lock")

    def test_trava_ocupada_nao_chama_processar_e_devolve_0(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {
            "ANUNCIO_ROOT": t,
            "OPENPORT_URL": "https://ilheus.codeba.gov.br/qas/openportcodeba/",
        }):
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
            trava.liberar(lock)

    def test_ocupada_notifica_uma_vez_por_episodio(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {
            "ANUNCIO_ROOT": t,
            "OPENPORT_URL": "https://ilheus.codeba.gov.br/qas/openportcodeba/",
        }):
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
            self.assertTrue(trava.adquirir(root / "logs" / "servico.lock"))
            trava.liberar(root / "logs" / "servico.lock")

    def test_producao_sem_autorizacao_nao_inicia_ciclo(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {
            "ANUNCIO_ROOT": t,
            "OPENPORT_URL": "https://openportilheus.codeba.gov.br/openportcodeba/",
        }, clear=False):
            os.environ.pop("PERMITIR_PROD", None)
            os.environ.pop("CONFIRMAR_ANUNCIO", None)
            chamadas = []
            rc = monitor_fila.modo_servico(
                0.01, True, processar_fn=lambda root, cfg: chamadas.append(1))
            self.assertEqual(rc, 2)
            self.assertEqual(chamadas, [])

    def test_producao_sem_confirmacao_nao_inicia_ciclo(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {
            "ANUNCIO_ROOT": t,
            "OPENPORT_URL": "https://openportilheus.codeba.gov.br/openportcodeba/",
            "PERMITIR_PROD": "1",
        }, clear=False):
            os.environ.pop("CONFIRMAR_ANUNCIO", None)
            chamadas = []
            rc = monitor_fila.modo_servico(
                0.01, True, processar_fn=lambda root, cfg: chamadas.append(1))
            self.assertEqual(rc, 2)
            self.assertEqual(chamadas, [])

    def test_url_nao_reconhecida_e_bloqueada_mesmo_com_flags(self):
        with TemporaryDirectory() as t, patch.dict(os.environ, {
            "ANUNCIO_ROOT": t,
            "OPENPORT_URL": "https://example.invalid/qas/openportcodeba/",
            "PERMITIR_PROD": "1",
            "CONFIRMAR_ANUNCIO": "1",
        }):
            chamadas = []
            rc = monitor_fila.modo_servico(
                0.01, True, processar_fn=lambda root, cfg: chamadas.append(1))
            self.assertEqual(rc, 2)
            self.assertEqual(chamadas, [])


if __name__ == "__main__":
    unittest.main()
