import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import lookup_engine


class TestNormalizar(unittest.TestCase):
    def test_remove_acento_e_maiuscula(self):
        self.assertEqual(lookup_engine.normalizar("Ilhéus"), "ILHEUS")

    def test_colapsa_espacos(self):
        self.assertEqual(lookup_engine.normalizar("  MARINAV   LTDA "), "MARINAV LTDA")


class TestConsultas(unittest.TestCase):
    def test_termo_simples_gera_prefixos_decrescentes(self):
        self.assertEqual(lookup_engine.consultas("MARINAV"),
                         [("descricao", "MARINAV"), ("descricao", "MARINA"),
                          ("descricao", "MARIN"), ("descricao", "MARI")])

    def test_preserva_acento_no_termo(self):
        self.assertEqual(lookup_engine.consultas("Ilhéus")[0], ("descricao", "Ilhéus"))

    def test_tira_ultima_palavra_antes_de_truncar(self):
        seq = lookup_engine.consultas("MARINAV LTDA")
        self.assertEqual(seq[0], ("descricao", "MARINAV LTDA"))
        self.assertEqual(seq[1], ("descricao", "MARINAV"))

    def test_codigo_com_nome_vira_filtro_de_codigo(self):
        seq = lookup_engine.consultas("30010 - MARINAV")
        self.assertIn(("codigo", "30010"), seq)

    def test_codigo_puro_tambem_vira_filtro_de_codigo(self):
        seq = lookup_engine.consultas("30010")
        self.assertIn(("codigo", "30010"), seq)

    def test_nome_com_espaco_nao_vira_filtro_de_codigo(self):
        seq = lookup_engine.consultas("MARINAV LTDA")
        self.assertNotIn(("codigo", "MARINAV LTDA"), seq)

    def test_termo_vazio_nao_gera_consulta(self):
        self.assertEqual(lookup_engine.consultas("   "), [])


class TestPontuar(unittest.TestCase):
    def test_igualdade_exata(self):
        self.assertEqual(lookup_engine.pontuar("MARINAV", "MARINAV"), 1.0)

    def test_igualdade_ignora_acento_e_caixa(self):
        self.assertEqual(lookup_engine.pontuar("ilheus", "Ilhéus"), 1.0)

    def test_descricao_comeca_com_o_termo(self):
        self.assertGreater(lookup_engine.pontuar("MARINAV", "MARINAV LTDA"), 0.7)

    def test_termo_comeca_com_a_descricao(self):
        self.assertGreater(lookup_engine.pontuar("MARINAV LTDA", "MARINAV"), 0.5)

    def test_sem_relacao_nao_pontua(self):
        self.assertEqual(lookup_engine.pontuar("MARINAV", "INTERMARIT"), 0.0)


class TestEscolher(unittest.TestCase):
    def setUp(self):
        self.armador = next(c for c in lookup_engine.CAMPOS if c.chave == "armador")
        self.carga = next(c for c in lookup_engine.CAMPOS if c.chave == "carga")

    def test_escolhe_correspondencia_exata(self):
        linhas = [["", "60700", "AMELIA NAVIGATION"], ["", "60162", "Amelia ship"]]
        idx, cands = lookup_engine.escolher("AMELIA NAVIGATION", linhas, self.armador)
        self.assertEqual(idx, 0)
        self.assertEqual(cands[0]["codigo"], "60700")

    def test_uma_linha_so_e_escolhida(self):
        idx, _ = lookup_engine.escolher("MARINAV", [["", "30010", "MARINAV"]], self.armador)
        self.assertEqual(idx, 0)

    def test_ambiguidade_nao_adivinha(self):
        linhas = [["", "60700", "AMELIA NAVIGATION"], ["", "60162", "Amelia ship"]]
        idx, cands = lookup_engine.escolher("AMELIA", linhas, self.armador)
        self.assertIsNone(idx)
        self.assertEqual(len(cands), 2)

    def test_sem_resultado_devolve_lista_vazia(self):
        idx, cands = lookup_engine.escolher("NADA", [], self.armador)
        self.assertIsNone(idx)
        self.assertEqual(cands, [])

    def test_carga_compara_com_a_mercadoria_completa(self):
        linhas = [["", "02061000", "MIUDEZAS COMESTIVEIS", "2",
                   "CARNES E MIUDEZAS, COMESTIVEIS.",
                   "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS"]]
        idx, _ = lookup_engine.escolher(
            "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS", linhas, self.carga)
        self.assertEqual(idx, 0)

    def test_carga_usa_o_indice_da_mercadoria_completa(self):
        # Grade medida no QAS: ["", cod, "Descricao Resumida", "Cod Grupo",
        # "Grupo Mercadoria", "Mercadoria", "", ""]. A mercadoria completa esta
        # no indice 5, nao no 6.
        linha = ["", "02061000", "MIUDEZAS COMESTIVEIS", "2",
                 "CARNES E MIUDEZAS, COMESTIVEIS.",
                 "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS", "", ""]
        self.assertEqual(self.carga.cols_descricao, (2, 5))
        idx, cands = lookup_engine.escolher(
            "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS", [linha], self.carga)
        self.assertEqual(idx, 0)
        self.assertEqual(cands[0]["descricao"],
                         "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS")

    def test_berco_descreve_pelo_nome_do_berco(self):
        # Grade medida no QAS: ["", cod, "BERCO 101", "1", "1", "CAIS COMERCIAL"].
        berco = next(c for c in lookup_engine.CAMPOS if c.chave == "berco")
        self.assertEqual(berco.cols_descricao, (2,))
        idx, cands = lookup_engine.escolher(
            "BERÇO 101", [["", "101", "BERÇO 101", "1", "1", "CAIS COMERCIAL"]], berco)
        self.assertEqual(idx, 0)
        self.assertEqual(cands[0]["descricao"], "BERÇO 101")


class TestCampos(unittest.TestCase):
    def test_oito_campos_na_ordem_do_bloco_3(self):
        self.assertEqual([c.chave for c in lookup_engine.CAMPOS],
                         ["porto_ant", "porto_prox", "armador", "afretador",
                          "agencia", "berco", "operador", "carga"])

    def test_todo_campo_tem_lupa_e_filtros(self):
        for c in lookup_engine.CAMPOS:
            self.assertTrue(c.seletor_lupa.startswith("#ANUM_"), c.chave)
            self.assertTrue(c.filtro_descricao, c.chave)
            self.assertTrue(c.filtro_codigo, c.chave)
            self.assertEqual(c.col_codigo, 1, c.chave)


if __name__ == "__main__":
    unittest.main()
