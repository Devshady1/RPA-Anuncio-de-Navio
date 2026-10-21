import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import limpar_evidencias  # noqa: E402


class TestLimpeza(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="limpeza_"))
        limpar_evidencias.ROOT = self.tmp
        self.screens = self.tmp / "screenshots"
        self.screens.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _criar(self, nome, dias):
        p = self.screens / nome
        p.write_text("x", encoding="utf-8")
        quando = datetime.now() - timedelta(days=dias)
        import os
        os.utime(p, (quando.timestamp(), quando.timestamp()))
        return p

    def test_sem_executar_nada_apaga(self):
        self._criar("velho.png", 90)
        self._criar("novo.png", 2)
        velhos = limpar_evidencias._maiores_que(datetime.now() - timedelta(days=30), ["screenshots"])
        self.assertEqual([p.name for p in velhos], ["velho.png"])
        self.assertTrue((self.screens / "velho.png").exists(),
                        "dry-run removeu arquivo!")

    def test_preserva_arquivos_de_auditoria(self):
        self._criar("run_audit.bat", 999)
        velhos = limpar_evidencias._maiores_que(datetime.now() - timedelta(days=1), ["screenshots"])
        self.assertEqual(velhos, [])


if __name__ == "__main__":
    unittest.main()
