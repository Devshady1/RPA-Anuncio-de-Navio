import os
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


# URLs base do OpenPort. QAS = homologacao, PROD = oficial (padrao de operacao).
URL_QAS = "https://ilheus.codeba.gov.br/qas/openportcodeba/"
URL_PROD = "https://openportilheus.codeba.gov.br/openportcodeba/"
URL_PADRAO = URL_QAS
KEYCHAIN_SERVICE = "com.codeba.anuncionavio.openport"
logger = logging.getLogger("anuncio.config")

# Classificacao padrao do anuncio (decisao de 14/10/2026): todo anuncio sai
# como LONGO CURSO / movimentacao de carga / exportacao / solido, e a correcao
# passa a ser manual caso a operacao seja diferente. Assim a ficha do agente
# maritimo nao pergunta classificacao - ele nao tem esse dado de cabeça.
CLASSIFICACAO_PADRAO = {
    "tipo_viagem": "1",
    "tipo_operacao": "1",
    "sentido": "1",
    "natureza": "1",
}


def aplicar_classificacao_padrao(campos: dict) -> dict:
    """Preenche CLASSIFICACAO_PADRAO nos campos de classificacao vazios."""
    for chave, valor in CLASSIFICACAO_PADRAO.items():
        if not (campos.get(chave) or "").strip():
            campos[chave] = valor
    return campos


def detectar_ambiente(url: str) -> str:
    """Classifica apenas os endpoints oficiais; URLs desconhecidas falham fechadas."""
    try:
        parsed = urlsplit(url or "")
        host = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/")
        port = parsed.port
    except ValueError:
        return "DESCONHECIDO"

    if (
        parsed.scheme.lower() != "https"
        or port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return "DESCONHECIDO"
    if host == "ilheus.codeba.gov.br" and path == "/qas/openportcodeba":
        return "QAS"
    if host == "openportilheus.codeba.gov.br" and path == "/openportcodeba":
        return "PRODUCAO"
    return "DESCONHECIDO"


def _senha_keychain() -> str:
    """Busca senha no Keychain do macOS sem passar por shell nem registrar o segredo."""
    if sys.platform != "darwin":
        return ""
    try:
        resultado = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Nao foi possivel consultar a senha no Keychain: %s", type(exc).__name__)
        return ""
    if resultado.returncode != 0:
        logger.warning("Senha do OpenPort nao encontrada no Keychain (%s).", resultado.returncode)
        return ""
    return resultado.stdout.rstrip("\r\n")


@dataclass(frozen=True)
class Config:
    url: str
    login: str
    senha: str
    headless: bool
    primeiro_plano: bool
    timeout_ms: int
    slow_mo_ms: int
    pausa_visual_ms: int
    manter_aberto_seg: int
    project_root: Path
    manter_aberto: bool = False
    ambiente: str = "QAS"
    css: dict = field(default_factory=dict)
    opcoes: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, dotenv_path=None, url_override: str | None = None) -> "Config":
        load_dotenv(dotenv_path)
        primeiro_plano = os.getenv("PRIMEIRO_PLANO", "true").lower() in ("1", "true", "yes", "sim")
        headless = os.getenv("HEADLESS", "false").lower() in ("1", "true", "yes", "sim")
        root_env = os.getenv("ANUNCIO_ROOT")
        project_root = Path(root_env).resolve() if root_env else Path(__file__).resolve().parent.parent.parent

        css = {
            "login": "input#User",
            "senha": "input#Pass",
            "entrar": "button#Entrar",
            "menu_acesso": "input#txtMenuAccess",
            # 2001 — listagem de programacao (filtros + tabela de resultado)
            "btn_filtrar_2001": "button#BPESQUISAR",
            "lista_2001": "table#TQuery",
            "modificar_2001": "a[title='Modificar']",
            "eta_ini_2001": "#SqlDAT_ETAIni",
            "eta_fim_2001": "#SqlDAT_ETAFim",
            "status_2001": "#sqlFLG_STATUS",
            # 2003 — botoes toolbar (outerHTML confirmado)
            "btn_novo_lista": "button#INSERIR",
            "btn_novo": "button#NOVO",
            "btn_gravar": "button#GRAVAR",
            "btn_verificar": "button#VERIFICAR",
            "btn_confirmar": "button#CONFIRMAR",
            # 2003 — bloco 1 chave (visivel _2, hidden base auto)
            "imo": "#NUM_NAVIO_2",
            "imo_hidden": "#NUM_NAVIO",
            "navio_nome": "#NUM_NAVIO_3",
            "viagem": "#COD_VIAGEM",
            "tipo_viagem": "select#TIP_VIAGEM",
            "tipo_operacao": "select#NUM_TIPO_OPERACAO",
            "sentido": "select#TIP_SENTIDO_VIAGEM",
            "natureza": "select#NUM_NATUREZA_OPERACAO",
            "status": "select#FLG_STATUS",
            # 2003 — datas (data + hora _2)
            "eta_data": "#DAT_ETA",
            "eta_hora": "#DAT_ETA_2",
            "etb_data": "#DAT_ETB",
            "etb_hora": "#DAT_ETB_2",
            "etc_data": "#DAT_ETC",
            "etc_hora": "#DAT_ETC_2",
            "ets_data": "#DAT_ETS",
            "ets_hora": "#DAT_ETS_2",
            # 2003 — lookups: input visivel _2 + hidden base + lupa ANUM_*
            "agencia": "#NUM_AGENCIA_2",
            "agencia_hidden": "#NUM_AGENCIA",
            "agencia_lupa": "#ANUM_AGENCIA",
            "porto_ant": "#NUM_PORTO_ANT_2",
            "porto_ant_hidden": "#NUM_PORTO_ANT",
            "porto_prox": "#NUM_PORTO_PROX_2",
            "porto_prox_hidden": "#NUM_PORTO_PROX",
            "armador": "#NUM_ARMADOR_2",
            "armador_hidden": "#NUM_ARMADOR",
            "afretador": "#NUM_AFRETADOR_2",
            "afretador_hidden": "#NUM_AFRETADOR",
            "berco": "#NUM_BERCO_2",
            "berco_hidden": "#NUM_BERCO",
            "operador": "#NUM_OPERADOR_2",
            "operador_hidden": "#NUM_OPERADOR",
            "carga": "#NUM_TIP_MERCAD_2",
            "carga_hidden": "#NUM_TIP_MERCAD",
            # 2003 — calado / mercadoria direto
            "calado_cheg_proa": "#MED_CALADO_CHEGADA_PROA",
            "calado_cheg_popa": "#MED_CALADO_CHEGADA_POPA",
            "calado_sai_proa": "#MED_CALADO_SAIDA_PROA",
            "calado_sai_popa": "#MED_CALADO_SAIDA_POPA",
            "qtd_carga": "#QTD_CARGA",
            "tons_prev": "#MED_TONS_PREV",
            "duv": "#COD_DUV",
        }

        opcoes = {
            "tipo_viagem": {"1": "LONGO CURSO", "2": "CABOTAGEM", "3": "APOIO MARITIMO", "4": "APOIO PORTUARIO", "5": "NAVEGACAO INTERIOR"},
            "sentido": {"1": "Exportacao", "2": "Importacao", "3": "Exportacao & Importacao"},
            "tipo_operacao": {"1": "Movimentacao de Carga", "2": "Apoio", "4": "Passageiro", "5": "Marinha", "6": "Abastecimento", "7": "Reparo/Manutencao", "8": "Misto", "10": "Estadia", "11": "Retirada de Residuos"},
            "natureza": {"1": "SOLIDO", "2": "LIQUIDO", "3": "GASOSO", "4": "CARGA GERAL", "5": "CONTEINER", "6": "PASSAGEIROS"},
        }

        senha = os.getenv("OPENPORT_SENHA", "")
        if not senha:
            senha = _senha_keychain()

        return cls(
            url=url_override or os.getenv("OPENPORT_URL", URL_PADRAO),
            login=os.getenv("OPENPORT_LOGIN", ""),
            senha=senha,
            headless=headless,
            primeiro_plano=primeiro_plano,
            timeout_ms=int(os.getenv("TIMEOUT_MS", "30000")),
            slow_mo_ms=int(os.getenv("SLOW_MO_MS", "300")),
            pausa_visual_ms=int(os.getenv("PAUSA_VISUAL_MS", "500")),
            manter_aberto_seg=int(os.getenv("MANTER_ABERTO_SEG", "60")),
        manter_aberto=os.getenv("MANTER_ABERTO", "false").lower() in ("1", "true", "yes", "sim"),
            project_root=project_root,
            ambiente=detectar_ambiente(url_override or os.getenv("OPENPORT_URL", URL_PADRAO)),
            css=css,
            opcoes=opcoes,
        )
