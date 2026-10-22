"""Entrada via JSON (substitui input()) — contrato de ingestao da fila.

Contrato da pasta:
    dados_rpa/*.json            -> pendentes (um anuncio por arquivo)
    dados_rpa/processados/*.json -> ja executados com sucesso (nao reprocessa)
    dados_rpa/erro/*.json        -> falhas (opcional, p/ triagem manual)

Qualquer produtor (metodo de insercao manual, planilha ou integrador do QA)
pode gravar o JSON na raiz de dados_rpa/ com nomes amigaveis
(nome_navio, imo, calado, eta, ...). Este modulo normaliza
para as chaves internas que `anuncio.criar_anuncio()` espera
(imo, viagem, tipo_viagem, eta_data, eta_hora, ...).

Uso tipico (ver run.py --fila):
    pendentes = listar_pendentes(pasta)
    for path in pendentes:
        dados = carregar_anuncio(path)   # <- substitui wizard.coletar()
        duv = executar_um(cfg, dados)    # <- automacao OpenPort inalterada
        finalizar_sucesso(path, duv)     # <- move p/ processados/
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from anuncio_navio import config

logger = logging.getLogger("anuncio.fila_json")

# Campos minimos para o OpenPort 2003 nao rejeitar de cara.
OBRIGATORIOS = ("imo", "viagem", "tipo_viagem", "tipo_operacao", "sentido", "natureza")

# Aliases que o produtor (formulario/planilha/integrador) pode gerar -> chave interna.
# Ex.: {"nome_navio": "...", "calado_chegada_proa": "5"} vira chave valida.
ALIASES = {
    "nome_navio": "navio_nome",          # informativo, anuncio.py so loga
    "navio": "navio_nome",
    "num_navio": "imo",
    "numero_navio": "imo",
    "capitania": "imo",
    "cod_viagem": "viagem",
    "eta": "eta_data",
    "etb": "etb_data",
    "etc": "etc_data",
    "ets": "ets_data",
    # calado agrupado: {"calado": {"chegada_proa": "5", ...}} tratado em _achatar()
    "calado_chegada_proa": "calado_cheg_proa",
    "calado_chegada_popa": "calado_cheg_popa",
    "calado_saida_proa": "calado_sai_proa",
    "calado_saida_popa": "calado_sai_popa",
    "unidades": "qtd",
    "qtd_carga": "qtd",
    "toneladas": "tons",
    "tons_previstas": "tons",
    "carga_predominante": "carga",
    "ultimo_porto": "porto_ant",
    "proximo_porto": "porto_prox",
}


def pasta_dados(project_root: Path, pasta: str | Path | None = None) -> Path:
    """Resolve a pasta de entrada. Padrao: <ROOT>/dados_rpa."""
    if pasta:
        return Path(pasta).resolve()
    return Path(project_root).resolve() / "dados_rpa"


def listar_pendentes(pasta: str | Path) -> list[Path]:
    """Busca *.json pendentes (ordenado). Ignora subpastas processados/ e erro/."""
    base = Path(pasta).resolve()
    base.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(base.glob("*.json"))  # glob nao-recursivo: nao pega processados/
    logger.info(f"{len(arquivos)} pendente(s) em {base}")
    return arquivos


def _achatar_calado(d: dict) -> dict:
    """Aceita 'calado': {chegada_proa, ...} ou 'calado_chegada_proa' avulso."""
    cal = d.pop("calado", None)
    if isinstance(cal, dict):
        mapa = {
            "chegada_proa": "calado_cheg_proa",
            "chegada_popa": "calado_cheg_popa",
            "saida_proa": "calado_sai_proa",
            "saida_popa": "calado_sai_popa",
        }
        for k, interno in mapa.items():
            if cal.get(k) is not None and not d.get(interno):
                d[interno] = str(cal[k])
    return d


def _separar_data_hora(d: dict) -> dict:
    """Aceita 'eta': '22/09/2026 23:00' ou 'eta_data': '22/09/2026 23:00' e divide."""
    for k in ("eta", "etb", "etc", "ets"):
        v = d.get(k)
        if isinstance(v, str) and v.strip() and not d.get(f"{k}_data"):
            partes = v.strip().split()
            d[f"{k}_data"] = partes[0]
            if len(partes) > 1 and not d.get(f"{k}_hora"):
                d[f"{k}_hora"] = partes[1]
        # caso o produtor mandou data+hora juntos em eta_data
        v2 = d.get(f"{k}_data")
        if isinstance(v2, str) and " " in v2.strip() and not d.get(f"{k}_hora"):
            partes = v2.strip().split()
            d[f"{k}_data"], d[f"{k}_hora"] = partes[0], partes[1]
    return d


def normalizar(bruto: dict) -> dict:
    """Converte JSON de entrada -> dict interno. Tudo vira str (o browser espera str)."""
    d = dict(bruto)
    d = _achatar_calado(d)
    # aplica aliases sem sobrescrever valor ja existente
    for apelido, interno in ALIASES.items():
        if apelido in d and d[apelido] not in (None, "") and not d.get(interno):
            d[interno] = d.pop(apelido)
        elif apelido in d and interno in d:
            d.pop(apelido, None)
    d = _separar_data_hora(d)
    # garante todas as chaves que anuncio.py le com .get()
    esperadas = (
        "imo", "viagem", "tipo_viagem", "tipo_operacao", "sentido", "natureza",
        "eta_data", "eta_hora", "etb_data", "etb_hora", "etc_data", "etc_hora",
        "ets_data", "ets_hora", "porto_ant", "porto_prox", "armador", "afretador",
        "agencia", "berco", "operador",
        "calado_cheg_proa", "calado_cheg_popa", "calado_sai_proa", "calado_sai_popa",
        "carga", "qtd", "tons",
    )
    limpo = {k: ("" if d.get(k) is None else str(d.get(k)).strip()) for k in esperadas}
    # QAS usa virgula decimal: "8.30" vira "830,00" se mandado com ponto.
    for k in ("calado_cheg_proa", "calado_cheg_popa", "calado_sai_proa",
              "calado_sai_popa", "tons", "loa", "qtd"):
        if limpo.get(k):
            limpo[k] = limpo[k].replace(".", ",")
    # preserva extras informativos (ex. nome_navio, loa/tpb, documentos) sem quebrar nada
    if bruto.get("nome_navio"):
        limpo["navio_nome_ref"] = str(bruto["nome_navio"]).strip()
    # codigo de fallback dos lookups: o texto do agente vai intacto e o popup do
    # OpenPort resolve; o codigo do CSV local viaja ao lado, para quando o
    # popup nao conhecer o cadastro.
    for k in ("agencia", "armador", "operador", "porto_ant", "porto_prox",
              "berco", "afretador", "carga"):
        if d.get(k + "_codigo"):
            limpo[k + "_codigo"] = str(d[k + "_codigo"]).strip()
    for extra in ("loa", "tpb"):
        if d.get(extra) not in (None, "") and extra not in limpo:
            limpo[extra] = str(d[extra]).strip().replace(".", ",")
    for extra in ("documentos", "navio_nome_ref"):
        if d.get(extra) not in (None, "") and extra not in limpo:
            limpo[extra] = d[extra]
    # Classificacao: padrao 1/1/1/1 quando nao informada (a ficha nao pergunta
    # mais; correcao manual quando a operacao for diferente).
    config.aplicar_classificacao_padrao(limpo)
    return limpo


# Encodings tentados ao ler o JSON de entrada. `utf-8-sig` cobre BOM (default de
# ferramentas do Windows: PowerShell 5.1, Notepad antigo, .NET com UTF8Encoding(true));
# `cp1252` cobre produtores legados. O projeto sempre grava utf-8 sem BOM, entao a
# primeira tentativa resolve para os arquivos internos.
ENCODINGS_ENTRADA = ("utf-8-sig", "cp1252")


def _ler_texto_entrada(p: Path) -> str:
    """Le o JSON de entrada tolerando BOM e produtores legados (ver ENCODINGS_ENTRADA)."""
    ultimo: UnicodeDecodeError | None = None
    for enc in ENCODINGS_ENTRADA:
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError as e:
            ultimo = e
    raise ValueError(
        f"{p.name}: nao foi possivel decodificar como {', '.join(ENCODINGS_ENTRADA)}: {ultimo}"
    )


def carregar_anuncio(path: str | Path) -> dict:
    """Le e valida um JSON. Levanta ValueError/FileNotFoundError com msg clara.

    Esta funcao SUBSTITUI todas as chamadas input() do wizard.py.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSON nao encontrado: {p}")
    try:
        bruto = json.loads(_ler_texto_entrada(p))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON invalido em {p.name}: {e}") from e
    if not isinstance(bruto, dict):
        raise ValueError(f"{p.name}: esperado um objeto JSON, veio {type(bruto).__name__}")
    dados = normalizar(bruto)
    faltando = [k for k in OBRIGATORIOS if not dados.get(k)]
    if faltando:
        raise ValueError(f"{p.name}: campos obrigatorios ausentes: {', '.join(faltando)}")
    logger.info(f"Carregado {p.name}: IMO {dados['imo']} Viagem {dados['viagem']}")
    return dados


def finalizar_sucesso(path: str | Path, duv: str = "") -> Path:
    """Move o JSON processado para dados_rpa/processados/ com carimbo de data + DUV.

    Retorna o caminho de destino. Nao reprocessa: listar_pendentes() so olha *.json
    na raiz de dados_rpa/, entao o movido sai da fila automaticamente.
    """
    return _arquivar(path, "processados", duv)


def finalizar_duplicado(path: str | Path) -> Path:
    """Move p/ dados_rpa/duplicados/ um anuncio barrado pela anti-duplicidade.

    Antes ia para processados/ igual a um sucesso, o que apagava a evidencia
    de que o anuncio NAO foi hecho — com a chave agora sequencial isso deve
    ser raro, mas o registro importa.
    """
    return _arquivar(path, "duplicados", "")


def _arquivar(path: str | Path, subpasta: str, duv: str) -> Path:
    origem = Path(path).resolve()
    destino_dir = origem.parent / subpasta
    destino_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufixo = f"__DUV{duv}" if duv else ""
    destino = destino_dir / f"{origem.stem}__{ts}{sufixo}{origem.suffix}"
    shutil.move(str(origem), str(destino))
    logger.info(f"Movido p/ {subpasta}/: {destino.name}")
    return destino


def finalizar_dryrun(path: str | Path) -> Path:
    """Move JSON validado em --dry-run para processados/ com marcador __DRYRUN.

    Evita que o monitor reencontre o mesmo arquivo no ciclo seguinte.
    ATENCAO: dry-run consome a fila — o arquivo movido NAO foi anunciado
    de fato. Para executar o RPA real depois, mova-o de volta para dados_rpa/.
    """
    origem = Path(path).resolve()
    destino_dir = origem.parent / "processados"
    destino_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = destino_dir / f"{origem.stem}__{ts}__DRYRUN{origem.suffix}"
    shutil.move(str(origem), str(destino))
    logger.info(f"Dry-run OK, movido p/ processados: {destino.name}")
    return destino


def finalizar_erro(path: str | Path, erro: Exception) -> Path:
    """Move JSON com falha para dados_rpa/erro/ preservando motivo em .txt lado a lado."""
    origem = Path(path).resolve()
    destino_dir = origem.parent / "erro"
    destino_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = destino_dir / f"{origem.stem}__{ts}_ERRO{origem.suffix}"
    shutil.move(str(origem), str(destino))
    (destino.with_suffix(".log.txt")).write_text(f"{type(erro).__name__}: {erro}", encoding="utf-8")
    logger.warning(f"Movido p/ erro: {destino.name}")
    return destino
