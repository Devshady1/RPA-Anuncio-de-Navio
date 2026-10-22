import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import anuncio, lookup_engine


class TestCamposLookup(unittest.TestCase):
    def test_so_campos_preenchidos_e_na_ordem(self):
        d = {"carga": "02061000", "armador": "MARINAV", "operador": ""}
        got = anuncio._campos_lookup(d)
        self.assertEqual([c.chave for c, _, _ in got], ["armador", "carga"])

    def test_fallback_vem_do_codigo_local(self):
        d = {"armador": "MARINAV", "armador_codigo": "30010"}
        got = dict((c.chave, (t, fb)) for c, t, fb in anuncio._campos_lookup(d))
        self.assertEqual(got["armador"], ("MARINAV", "30010"))

    def test_campo_vazio_nao_entra(self):
        d = {"armador": "   ", "porto_ant": "Ilhéus"}
        got = anuncio._campos_lookup(d)
        self.assertEqual([c.chave for c, _, _ in got], ["porto_ant"])

    def test_codigo_escrito_pelo_operador_vira_fallback(self):
        # '30010 - MARINAV': o proprio codigo do operador e o fallback, para
        # quando o popup estiver fora do ar.
        d = {"armador": "30010 - MARINAV"}
        got = dict((c.chave, (t, fb)) for c, t, fb in anuncio._campos_lookup(d))
        self.assertEqual(got["armador"], ("30010 - MARINAV", "30010"))

    def test_codigo_puro_escrito_pelo_operador_vira_fallback(self):
        d = {"carga": "02061000"}
        got = dict((c.chave, (t, fb)) for c, t, fb in anuncio._campos_lookup(d))
        self.assertEqual(got["carga"], ("02061000", "02061000"))

    def test_nome_sem_codigo_nao_tem_fallback(self):
        d = {"armador": "MARINAV"}
        got = dict((c.chave, (t, fb)) for c, t, fb in anuncio._campos_lookup(d))
        self.assertEqual(got["armador"], ("MARINAV", ""))


class TestUsarFallback(unittest.TestCase):
    def test_popup_sem_resultado_usa_o_codigo_do_csv(self):
        self.assertTrue(anuncio._usar_fallback([], "30010"))

    def test_popup_ambiguo_nao_usa_o_codigo_do_csv(self):
        # Com candidatos, o popup ACHOU o cadastro e nao consegue escolher:
        # escolher pelo CSV local seria adivinhar (e o cadastro local e velho).
        cands = [{"codigo": "60700", "descricao": "AMELIA NAVIGATION"},
                 {"codigo": "60162", "descricao": "Amelia ship"}]
        self.assertFalse(anuncio._usar_fallback(cands, "60700"))

    def test_sem_codigo_local_nao_ha_fallback(self):
        self.assertFalse(anuncio._usar_fallback([], ""))

    def test_popup_com_linha_sem_nota_usa_o_codigo_do_csv(self):
        # Linha que nao casa nada e ruido do filtro, nao "achado": o CSV
        # local continua valendo (antes essa linha barrava a ficha).
        armador = next(c for c in lookup_engine.CAMPOS if c.chave == "armador")
        _, cands = lookup_engine.escolher(
            "MARINAV", [["", "99999", "OUTRA COISA"]], armador)
        self.assertTrue(anuncio._usar_fallback(cands, "30010"))


class TestCamposDoMotor(unittest.TestCase):
    def test_o_motor_cobre_os_campos_do_bloco_3(self):
        chaves = [c.chave for c in lookup_engine.CAMPOS]
        self.assertEqual(chaves, ["porto_ant", "porto_prox", "armador", "afretador",
                                  "agencia", "berco", "operador", "carga"])


if __name__ == "__main__":
    unittest.main()
