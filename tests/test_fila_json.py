import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import fila_json


class TestFilaJson(unittest.TestCase):
    def test_normalizar_aliases_e_data_hora(self):
        bruto = {
            "nome_navio": "VOYAGER",
            "num_navio": "9553256",
            "cod_viagem": "000003",
            "eta": "05/10/2026 07:30",
            "tipo_viagem": "1",
            "tipo_operacao": "1",
            "sentido": "1",
            "natureza": "1",
            "calado": {"chegada_proa": "8.30"},
        }
        dados = fila_json.normalizar(bruto)
        self.assertEqual(dados["imo"], "9553256")
        self.assertEqual(dados["viagem"], "000003")
        self.assertEqual(dados["eta_data"], "05/10/2026")
        self.assertEqual(dados["eta_hora"], "07:30")
        self.assertEqual(dados["calado_cheg_proa"], "8,30")
        self.assertEqual(dados["navio_nome_ref"], "VOYAGER")

    def test_normalizar_preserva_o_codigo_de_fallback_do_lookup(self):
        # O texto do agente vai intacto; o codigo do CSV local viaja ao lado
        # como fallback, para quando o popup do OpenPort nao conhecer o
        # cadastro. Sem isso o fallback morre no caminho da fila.
        bruto = dict(_payload_minimo())
        bruto["armador"] = "MARINAV"
        bruto["armador_codigo"] = "30010"
        dados = fila_json.normalizar(bruto)
        self.assertEqual(dados["armador"], "MARINAV")
        self.assertEqual(dados["armador_codigo"], "30010")

    def test_normalizar_nao_inventa_codigo_quando_nao_veio(self):
        dados = fila_json.normalizar(_payload_minimo())
        self.assertNotIn("armador_codigo", dados)

    def test_carregar_anuncio_exige_obrigatorios(self):
        caminho = ROOT / "dados_rpa" / "tmp_teste_sem_imo.json"
        caminho.write_text("{}", encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                fila_json.carregar_anuncio(caminho)
        finally:
            caminho.unlink(missing_ok=True)

    def test_carregar_anuncio_tolera_bom(self):
        caminho = ROOT / "dados_rpa" / "tmp_teste_bom.json"
        caminho.write_text(json.dumps(_payload_minimo()), encoding="utf-8-sig")
        try:
            self.assertEqual(fila_json.carregar_anuncio(caminho)["imo"], "9553256")
        finally:
            caminho.unlink(missing_ok=True)

    def test_carregar_anuncio_tolera_cp1252(self):
        caminho = ROOT / "dados_rpa" / "tmp_teste_cp1252.json"
        payload = _payload_minimo()
        payload["nome_navio"] = "NAVIO NÍQUEL"
        caminho.write_text(json.dumps(payload, ensure_ascii=False), encoding="cp1252")
        try:
            self.assertEqual(fila_json.carregar_anuncio(caminho)["navio_nome_ref"], "NAVIO NÍQUEL")
        finally:
            caminho.unlink(missing_ok=True)


def _payload_minimo() -> dict:
    return {
        "imo": "9553256",
        "viagem": "000009",
        "tipo_viagem": "1",
        "tipo_operacao": "1",
        "sentido": "1",
        "natureza": "1",
    }


if __name__ == "__main__":
    unittest.main()
