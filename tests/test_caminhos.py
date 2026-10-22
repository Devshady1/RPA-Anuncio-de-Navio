import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import caminhos


class TestCaminhos(unittest.TestCase):
    def test_home_usa_anuncio_root(self):
        with patch.dict(os.environ, {"ANUNCIO_ROOT": r"C:\tmp\anuncios"}):
            self.assertEqual(caminhos.home(), Path(r"C:\tmp\anuncios"))

    def test_layout_do_deploy(self):
        root = Path(r"C:\tmp\anuncios")
        self.assertEqual(caminhos.ficha(root), root / "ficha" / "ficha_anuncio_navio.xlsx")
        self.assertEqual(caminhos.arquivo_dir(root), root / "ficha" / "arquivo")
        self.assertEqual(caminhos.data_dir(root), root / "data")
        self.assertEqual(caminhos.logs_dir(root), root / "logs")
        self.assertEqual(caminhos.tmp_dir(root), root / "tmp")
        self.assertEqual(caminhos.json_dir(root), root / "data" / "json")
        self.assertEqual(caminhos.config_env(root), root / "config" / ".env")

    def test_home_sem_variavel_e_a_raiz_do_repo(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANUNCIO_ROOT", None)
            self.assertTrue((caminhos.home() / "run.py").exists())


if __name__ == "__main__":
    unittest.main()
