import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import config, fila_json, tabelas


class TestResolveCarga(unittest.TestCase):
    def test_codigo_de_8_digitos_passa_inteiro(self):
        self.assertEqual(tabelas.resolver_carga("26040000")[0], "26040000")

    def test_nome_inequivoco_resolve_sozinho(self):
        self.assertEqual(tabelas.resolver_carga("minerio de niquel")[0], "26040000")

    def test_nome_com_acento_resolve(self):
        self.assertEqual(tabelas.resolver_carga("minério de níquel")[0], "26040000")

    def test_nome_da_mercadoria_especifico(self):
        self.assertEqual(tabelas.resolver_carga("cimento portland")[0], "25232910")

    def test_nome_de_minerio_prefere_o_minerio(self):
        # 'niquel' sozinho bate em 4 codigos (minerio, sulfato, catalisador,
        # residuo). O residuo/derivado e saida de balanca: navio opera minerio.
        self.assertEqual(tabelas.resolver_carga("niquel")[0], "26040000")

    def test_outros_minerios_resolvem(self):
        self.assertEqual(tabelas.resolver_carga("manganes")[0], "26020010")
        self.assertEqual(tabelas.resolver_carga("cobalto")[0], "26050000")

    def test_nao_minerio_ambiguo_nao_adivinha(self):
        codigo, cands = tabelas.resolver_carga("soja")
        self.assertEqual(codigo, "")
        self.assertGreaterEqual(len(cands), 2)
        self.assertIn("12010010", [c for c, _ in cands])

    def test_dois_minerios_validos_continuam_ambiguos(self):
        codigo, cands = tabelas.resolver_carga("cromo")
        self.assertEqual(codigo, "")
        self.assertTrue(all("MINERIO" in d.upper() for _, d in cands))

    def test_mercadoria_fora_da_tabela(self):
        codigo, cands = tabelas.resolver_carga("minerio de ferro")
        self.assertEqual(codigo, "")
        self.assertEqual(cands, [])

    def test_residuo_nunca_resolve(self):
        # 18020000 = cascas/peliculas/desperdicios de cacau; 75030000 = residuos
        # de niquel. Saida de balanca: navio nao opera (regra do usuario).
        for termo in ("cascas de cacau", "18020000", "75030000",
                      "residuos de niquel", "desperdicio de cacau"):
            self.assertEqual(tabelas.resolver_carga(termo), ("", []), termo)

    def test_mercadoria_normal_nao_e_afetada(self):
        self.assertEqual(tabelas.resolver_carga("26040000")[0], "26040000")
        self.assertEqual(tabelas.resolver_carga("manteiga de cacau")[0], "18040000")


class TestClassificacaoPadrao(unittest.TestCase):
    def test_normalizar_aplica_padrao_1111(self):
        bruto = {"imo": "9553256", "viagem": "000008", "nome_navio": "VOYAGER"}
        d = fila_json.normalizar(bruto)
        self.assertEqual([d["tipo_viagem"], d["tipo_operacao"], d["sentido"], d["natureza"]],
                         ["1", "1", "1", "1"])

    def test_apelidos_comerciais_de_cacau(self):
        # A NCM nao usa a palavra 'amendoa'; o porto fala 'amendoa de cacau'.
        for termo in ("cacau", "amendoa de cacau", "cacau em amendoa",
                      "amêndoa de cacau"):
            self.assertEqual(tabelas.resolver_carga(termo)[0], "18010000", termo)

    def test_derivados_de_cacau_resolvem_separado(self):
        self.assertEqual(tabelas.resolver_carga("manteiga de cacau")[0], "18040000")

    def test_classificacao_informada_e_respeitada(self):
        bruto = {"imo": "9553256", "viagem": "000008", "tipo_viagem": "2", "sentido": "2"}
        d = fila_json.normalizar(bruto)
        self.assertEqual([d["tipo_viagem"], d["sentido"]], ["2", "2"])

    def test_padrao_e_valido_no_openport(self):
        from anuncio_navio import planilha
        for k, v in config.CLASSIFICACAO_PADRAO.items():
            self.assertIn(v, planilha.CODIGOS_VALIDOS[k])


if __name__ == "__main__":
    unittest.main()
