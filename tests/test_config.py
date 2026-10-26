import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import config
from anuncio_navio.config import URL_PROD, URL_QAS, detectar_ambiente


class TestDetectarAmbiente(unittest.TestCase):
    def test_configuracao_sem_url_define_qas_como_padrao(self):
        with patch.dict("os.environ", {}, clear=True):
            cfg = config.Config.from_env(dotenv_path=ROOT / "missing.env")

        self.assertEqual(cfg.url, URL_QAS)
        self.assertEqual(cfg.ambiente, "QAS")

    def test_classifica_endpoints_oficiais(self):
        self.assertEqual(detectar_ambiente(URL_QAS), "QAS")
        self.assertEqual(detectar_ambiente(URL_PROD), "PRODUCAO")

    def test_url_desconhecida_falha_fechada(self):
        urls = (
            "https://example.invalid/qas/openportcodeba/",
            "https://ilheus.codeba.gov.br.evil.invalid/qas/openportcodeba/",
            "https://ilheus.codeba.gov.br/qas/openportcodeba-evil/",
            "http://ilheus.codeba.gov.br/qas/openportcodeba/",
            "https://ilheus.codeba.gov.br:8443/qas/openportcodeba/",
            "https://ilheus.codeba.gov.br/qas/openportcodeba/?next=prod",
            "https://user@ilheus.codeba.gov.br/qas/openportcodeba/",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(detectar_ambiente(url), "DESCONHECIDO")

    def test_senha_keychain_no_macos(self):
        resultado = type("Resultado", (), {"returncode": 0, "stdout": "segredo\n"})()
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(config.sys, "platform", "darwin"), \
                patch.object(config.subprocess, "run", return_value=resultado) as executar:
            cfg = config.Config.from_env(dotenv_path=ROOT / "missing.env")

        self.assertEqual(cfg.senha, "segredo")
        executar.assert_called_once_with(
            ["security", "find-generic-password", "-s", config.KEYCHAIN_SERVICE, "-w"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_senha_de_env_tem_precedencia_sobre_keychain(self):
        with patch.dict("os.environ", {"OPENPORT_SENHA": "env-secret"}, clear=True), \
                patch.object(config.sys, "platform", "darwin"), \
                patch.object(config.subprocess, "run") as executar:
            cfg = config.Config.from_env(dotenv_path=ROOT / "missing.env")

        self.assertEqual(cfg.senha, "env-secret")
        executar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
