import os
import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import openpyxl

from anuncio_navio import config, exceptions, historico, servico, status

MODELO = Path(__file__).resolve().parents[1] / "src" / "anuncio_navio" / "recursos" / "ficha_modelo.xlsx"


class TestProcessar(unittest.TestCase):
    CAMPOS = {
        "C6": "VOYAGER", "C7": "9553256", "C8": "190", "C11": "Ilheus",
        "C12": "28/11/2026", "D12": "07:30", "C13": "29/11/2026", "D13": "08:00",
        "C14": "30/11/2026", "D14": "12:00", "C15": "30/11/2026", "D15": "19:00",
        "C16": "Santos", "C17": "BERÇO 101", "C19": "MIUDEZAS COMESTIVEIS",
        "C20": "1000", "C21": "1000", "C22": "8,30", "D22": "8,30",
        "C23": "8,30", "D23": "8,30", "C25": "MARINAV", "C26": "AMELIA",
        "C27": "INTERMARIT", "C28": "AEC SHIPPING",
    }

    def _ficha(self, root, campos=None):
        p = root / "ficha" / "ficha_anuncio_navio.xlsx"
        shutil.copyfile(MODELO, p)
        wb = openpyxl.load_workbook(p)
        for cel, v in (campos or self.CAMPOS).items():
            wb["Anúncio"][cel] = v
        wb.save(p)
        return p

    def _root_preenchido(self, t):
        root = Path(t)
        (root / "ficha").mkdir()
        self._ficha(root)
        return root

    def _cfg(self, root):
        return config.Config(
            url=config.URL_QAS, login="login", senha="senha", headless=True,
            primeiro_plano=True, timeout_ms=30000, slow_mo_ms=0, pausa_visual_ms=0,
            manter_aberto_seg=0, project_root=root, ambiente="QAS")

    def test_sucesso_arquiva_e_gera_nova(self):
        with TemporaryDirectory() as t:
            root = self._root_preenchido(t)
            cfg = self._cfg(root)
            avisos = []
            def anunciar(c, d):
                status.marcar_ok(c, d, "000010")   # executar_um real faz isso
                return "000010"
            r = servico.processar(root, cfg, executar=anunciar,
                                  notificar_fn=lambda ti, tx: avisos.append((ti, tx)))
            self.assertEqual(r.estado, "ok")
            self.assertEqual(r.duv, "000010")
            self.assertEqual(list((root / "ficha" / "arquivo").glob("*.xlsx"))[0].name.count("DUV000010"), 1)
            self.assertTrue((root / "ficha" / "ficha_anuncio_navio.xlsx").exists())
            self.assertEqual(historico.linhas(root)[-1][5], "OK")
            self.assertIn("DUV 000010", avisos[0][1])

    def test_invalida_mantem_a_ficha_e_nao_reserva_viagem(self):
        with TemporaryDirectory() as t:
            root = Path(t); (root / "ficha").mkdir()
            shutil.copyfile(MODELO, root / "ficha" / "ficha_anuncio_navio.xlsx")
            r = servico.processar(root, self._cfg(root), executar=lambda c, d: "x",
                                  notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "invalida")
            self.assertFalse((root / "ficha" / "arquivo").exists())
            self.assertFalse((root / "data" / "sequencia.json").exists())
            c3 = openpyxl.load_workbook(root / "ficha" / "ficha_anuncio_navio.xlsx")["Anúncio"]["C3"].value
            self.assertTrue(c3.startswith("NÃO FOI ENVIADO — faltam"))

    def test_pedido_grava_pedidos_e_mantem(self):
        with TemporaryDirectory() as t:
            root = self._root_preenchido(t)
            def falhar(c, d):
                raise exceptions.LookupError("PEDIDO: armador 'AMELIA' nao cadastrado.")
            r = servico.processar(root, self._cfg(root), executar=falhar,
                                  notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "falhou")
            self.assertIn("PEDIDO", (root / "data" / "pedidos.csv").read_text(encoding="utf-8"))
            self.assertTrue((root / "ficha" / "ficha_anuncio_navio.xlsx").exists())

    def test_duplicado_por_conteudo_nao_chama_o_robo(self):
        with TemporaryDirectory() as t:
            root = self._root_preenchido(t)
            cfg = self._cfg(root)
            chamou = []
            def anunciar(c, d):
                status.marcar_ok(c, d, "000010")
                return "000010"
            servico.processar(root, cfg, executar=anunciar,
                              notificar_fn=lambda ti, tx: None)
            # simula a ficha antiga (ja arquivada) re-salva por cima da nova
            arquivada = next((root / "ficha" / "arquivo").glob("*.xlsx"))
            p = root / "ficha" / "ficha_anuncio_navio.xlsx"
            shutil.copyfile(arquivada, p)
            velho = p.stat().st_mtime - 60
            os.utime(p, (velho, velho))
            r = servico.processar(root, self._cfg(root),
                                  executar=lambda c, d: chamou.append(1) or "000011",
                                  notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "duplicado")
            self.assertEqual(r.duv, "000010")
            self.assertEqual(chamou, [])

    def test_ficha_parada_nao_roda_de_novo(self):
        with TemporaryDirectory() as t:
            root = Path(t); (root / "ficha").mkdir()
            shutil.copyfile(MODELO, root / "ficha" / "ficha_anuncio_navio.xlsx")
            cfg = self._cfg(root)
            servico.processar(root, cfg, executar=lambda c, d: "x", notificar_fn=lambda ti, tx: None)
            r = servico.processar(root, cfg, executar=lambda c, d: "x", notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "sem_novidade")


if __name__ == "__main__":
    unittest.main()
