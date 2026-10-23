import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import historico


class TestHistorico(unittest.TestCase):
    def test_registrar_e_ler(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            historico.registrar(root, navio="VOYAGER", imo="9553256", viagem="000010",
                                duv="000010", resultado="OK", detalhe="Anúncio confirmado")
            historico.registrar(root, navio="VOYAGER", imo="9553256", viagem="000011",
                                resultado="FALHOU", detalhe="2 armadores com AMELIA")
            linhas = historico.linhas(root)
        self.assertEqual(linhas[0], historico.CABECALHO)
        self.assertEqual(len(linhas), 3)
        self.assertEqual(linhas[1][5], "OK")
        self.assertEqual(linhas[2][3:6], ("000011", "", "FALHOU"))

    def test_pedido_grava_data_tipo_texto(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            quando = datetime(2026, 10, 22, 14, 30)
            historico.pedido(root, tipo="armador", texto="AMELIA nao cadastrado", quando=quando)
            historico.pedido(root, tipo="carga", texto="ZZZ nao cadastrada", quando=quando)
            linhas = (root / "data" / "pedidos.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(linhas[0], "data,tipo,texto")
        self.assertEqual(len(linhas), 3)
        self.assertEqual(linhas[1], "22/10/2026 14:30,armador,AMELIA nao cadastrado")


if __name__ == "__main__":
    unittest.main()
