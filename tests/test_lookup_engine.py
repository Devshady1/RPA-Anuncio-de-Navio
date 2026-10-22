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
        # Depois da busca pela descricao vem a busca pelo CODIGO (palavra unica
        # pode ser codigo: porto 'BRIOS') e so entao os prefixos da descricao.
        self.assertEqual(lookup_engine.consultas("MARINAV"),
                         [("descricao", "MARINAV"), ("codigo", "MARINAV"),
                          ("descricao", "MARINA"),
                          ("descricao", "MARIN"), ("descricao", "MARI"),
                          ("descricao", "MAR")])

    def test_prefixo_minimo_tem_tres_letras(self):
        # Medido no QAS: 'ILH' acha Ilheus e 'ILHE' nao, porque o acento
        # quebra o prefixo a partir da 4a letra. Quem digita "Ilheus" sem
        # acento so resolve se a consulta descer ate 3 letras.
        self.assertIn(("descricao", "Ilh"), lookup_engine.consultas("Ilheus"))

    def test_termo_curto_nao_gera_prefixo_menor_que_o_proprio(self):
        self.assertEqual(lookup_engine.consultas("RIO"),
                         [("descricao", "RIO"), ("codigo", "RIO")])

    def test_nome_longo_degrada_por_palavra(self):
        # Medido no QAS: a descricao resumida da carga e o COMECO da
        # mercadoria completa ("MIUDEZAS COMESTIVEIS"). Truncar caractere a
        # caractere de "...BOVINO,FRESCAS" nunca chega nela.
        seq = lookup_engine.consultas(
            "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS")
        self.assertIn(("descricao", "MIUDEZAS COMESTIVEIS"), seq)

    def test_nome_longo_tenta_as_fronteiras_de_palavra_antes_dos_caracteres(self):
        seq = lookup_engine.consultas("MINERIOS DE NIQUEL E SEUS CONCENTRADOS")
        self.assertIn(("descricao", "MINERIOS DE NIQUEL"), seq)
        self.assertLess(seq.index(("descricao", "MINERIOS DE NIQUEL E SEUS")),
                        seq.index(("descricao", "MINERIOS DE NIQUEL")))

    def test_nao_consulta_termo_com_espaco_no_fim(self):
        seq = lookup_engine.consultas("MINERIOS DE NIQUEL E SEUS CONCENTRADOS")
        self.assertFalse([t for _, t in seq if t != t.strip()])

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

    def test_linha_sem_nota_nao_conta_como_candidato(self):
        # O popup pode devolver uma linha que nao casa nada (score 0.0). Ela
        # nao pode bloquear o fallback do CSV: sem candidato de verdade, o
        # popup NAO achou o cadastro.
        linhas = [["", "99999", "OUTRA COISA"]]
        idx, cands = lookup_engine.escolher("MARINAV", linhas, self.armador)
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


class TestTermoQueEhCodigo(unittest.TestCase):
    """A ficha do agente traz codigo em varios campos (porto, agencia...)."""

    def setUp(self):
        self.armador = next(c for c in lookup_engine.CAMPOS if c.chave == "armador")
        self.porto = next(c for c in lookup_engine.CAMPOS if c.chave == "porto_ant")

    def test_escolhe_a_linha_pelo_codigo(self):
        linhas = [["", "30010", "MARINAV"], ["", "30002", "INTERMARIT"]]
        idx, cands = lookup_engine.escolher("30010", linhas, self.armador)
        self.assertEqual(idx, 0)
        self.assertEqual(cands[0]["codigo"], "30010")

    def test_escolhe_a_linha_pelo_codigo_com_nome(self):
        linhas = [["", "30010", "MARINAV"]]
        idx, _ = lookup_engine.escolher("30010 - MARINAV", linhas, self.armador)
        self.assertEqual(idx, 0)

    def test_escolhe_a_linha_pelo_codigo_do_porto(self):
        linhas = [["", "BRIOS", "ILHEUS"]]
        idx, cands = lookup_engine.escolher("BRIOS", linhas, self.porto)
        self.assertEqual(idx, 0)
        self.assertEqual(cands[0]["descricao"], "ILHEUS")

    def test_codigo_igual_em_duas_linhas_nao_adivinha(self):
        linhas = [["", "30010", "MARINAV"], ["", "30010", "MARINAV LTDA"]]
        idx, cands = lookup_engine.escolher("30010", linhas, self.armador)
        self.assertIsNone(idx)
        self.assertEqual(len(cands), 2)

    def test_consulta_pelo_codigo_de_termo_de_uma_palavra(self):
        self.assertIn(("codigo", "BRIOS"), lookup_engine.consultas("BRIOS"))

    def test_consulta_pelo_codigo_vem_depois_da_descricao(self):
        seq = lookup_engine.consultas("BRIOS")
        self.assertLess(seq.index(("descricao", "BRIOS")), seq.index(("codigo", "BRIOS")))

    def test_nome_com_espaco_nao_vira_consulta_por_codigo(self):
        seq = lookup_engine.consultas("AMELIA NAVIGATION")
        self.assertNotIn(("codigo", "AMELIA NAVIGATION"), seq)


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
