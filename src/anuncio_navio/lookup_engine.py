"""Motor de decisao dos lookups do OpenPort (puro, sem navegador).

A consulta do OpenPort (popup "Localizar") busca por PREFIXO, e insensivel a
maiusculas mas sensivel a acento. Este modulo decide, sem tocar no navegador,
o que consultar e qual linha escolher.

- consultas(): lista ordenada de (campo_filtro, termo) a tentar no popup.
- pontuar(): nota de quanto a descricao casa com o que o operador escreveu.
- escolher(): escolhe a linha, ou recusa quando ha ambiguidade.

Nao adivinha: quando dois cadastros casam com o mesmo score, devolve None e
deixa a decisao para quem opera.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SEPARADORES = re.compile(r"^([A-Za-z0-9]+)\s*[-–—:]")
_NUMERICO = re.compile(r"^\d+$")


@dataclass(frozen=True)
class CampoLookup:
    """Como um campo do Bloco 3 se comporta no popup de consulta."""

    chave: str
    rotulo: str
    seletor_visivel: str
    seletor_hidden: str
    seletor_lupa: str
    filtro_descricao: str
    filtro_codigo: str
    col_codigo: int
    cols_descricao: tuple[int, ...]


CAMPOS: tuple[CampoLookup, ...] = (
    CampoLookup(
        chave="porto_ant",
        rotulo="PortoAnt",
        seletor_visivel="#NUM_PORTO_ANT_2",
        seletor_hidden="#NUM_PORTO_ANT",
        seletor_lupa="#ANUM_PORTO_ANT",
        filtro_descricao="sqlFiltroDescricao",
        filtro_codigo="sqlCOD_PORTO",
        col_codigo=1,
        cols_descricao=(2,),
    ),
    CampoLookup(
        chave="porto_prox",
        rotulo="PortoProx",
        seletor_visivel="#NUM_PORTO_PROX_2",
        seletor_hidden="#NUM_PORTO_PROX",
        seletor_lupa="#ANUM_PORTO_PROX",
        filtro_descricao="sqlFiltroDescricao",
        filtro_codigo="sqlCOD_PORTO",
        col_codigo=1,
        cols_descricao=(2,),
    ),
    CampoLookup(
        chave="armador",
        rotulo="Armador",
        seletor_visivel="#NUM_ARMADOR_2",
        seletor_hidden="#NUM_ARMADOR",
        seletor_lupa="#ANUM_ARMADOR",
        filtro_descricao="sqlFiltroDescricao",
        filtro_codigo="sqlCOD_EMPRESA",
        col_codigo=1,
        cols_descricao=(2,),
    ),
    CampoLookup(
        chave="afretador",
        rotulo="Afretador",
        seletor_visivel="#NUM_AFRETADOR_2",
        seletor_hidden="#NUM_AFRETADOR",
        seletor_lupa="#ANUM_AFRETADOR",
        filtro_descricao="sqlFiltroDescricao",
        filtro_codigo="sqlCOD_EMPRESA",
        col_codigo=1,
        cols_descricao=(2,),
    ),
    CampoLookup(
        chave="agencia",
        rotulo="Agencia",
        seletor_visivel="#NUM_AGENCIA_2",
        seletor_hidden="#NUM_AGENCIA",
        seletor_lupa="#ANUM_AGENCIA",
        filtro_descricao="sqlNOM_FANTASIA",
        filtro_codigo="SqlCOD_EMPRESA",
        col_codigo=1,
        cols_descricao=(2,),
    ),
    CampoLookup(
        chave="berco",
        rotulo="Berco",
        seletor_visivel="#NUM_BERCO_2",
        seletor_hidden="#NUM_BERCO",
        seletor_lupa="#ANUM_BERCO",
        filtro_descricao="sqlDCR_BERCO",
        filtro_codigo="sqlCOD_BERCO",
        col_codigo=1,
        cols_descricao=(2,),
    ),
    CampoLookup(
        chave="operador",
        rotulo="Operador",
        seletor_visivel="#NUM_OPERADOR_2",
        seletor_hidden="#NUM_OPERADOR",
        seletor_lupa="#ANUM_OPERADOR",
        filtro_descricao="sqlFiltroDescricao",
        filtro_codigo="sqlCOD_EMPRESA",
        col_codigo=1,
        cols_descricao=(2,),
    ),
    CampoLookup(
        chave="carga",
        rotulo="Carga",
        seletor_visivel="#NUM_TIP_MERCAD_2",
        seletor_hidden="#NUM_TIP_MERCAD",
        seletor_lupa="#ANUM_TIP_MERCAD",
        filtro_descricao="sqlDCR_TIP_MERCAD",
        filtro_codigo="sqlCOD_TIP_MERCAD",
        col_codigo=1,
        cols_descricao=(2, 5),
    ),
)


def normalizar(txt: str) -> str:
    """Sem acento, sem espaco duplicado, em maiusculas."""
    if not txt:
        return ""
    limpo = unicodedata.normalize("NFD", str(txt))
    limpo = "".join(c for c in limpo if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", limpo).strip().upper()


def consultas(termo: str, minimo: int = 3, limite: int = 6) -> list[tuple[str, str]]:
    """Consultas a tentar no popup, em ordem: (campo_filtro, termo).

    campo_filtro e "descricao" ou "codigo". O texto do operador sempre vem
    primeiro pela descricao, para nao gastar uma ida ao servidor com um
    codigo que talvez nem exista.

    minimo=3 por medicao no QAS: a busca e sensivel a acento, e 'ILH' acha
    "Ilheus" enquanto 'ILHE' nao acha - por isso o prefixo nao pode parar
    em 4 letras.
    """
    bruto = str(termo or "").strip()
    if not bruto:
        return []

    codigo = None
    achado = _SEPARADORES.match(bruto)
    if achado and achado.group(1) != bruto:
        codigo = achado.group(1)
    if codigo is None and _NUMERICO.match(bruto) and len(bruto) >= 3:
        codigo = bruto

    seq: list[tuple[str, str]] = []
    if _NUMERICO.match(bruto):
        seq.append(("codigo", bruto))
    else:
        seq.append(("descricao", bruto))
    if codigo is not None:
        seq.append(("codigo", codigo))
    elif " " not in bruto:
        # Palavra unica pode ser CODIGO (porto 'BRIOS', agencia '30010'):
        # a busca por descricao nao acha nada e o filtro de codigo acha.
        seq.append(("codigo", bruto))

    if codigo is not None:
        base, campo_base = codigo, "codigo"
    elif " " in bruto:
        base, campo_base = bruto.rsplit(" ", 1)[0], "descricao"
    else:
        base, campo_base = bruto, "descricao"
    seq.append((campo_base, base))
    for tamanho in range(len(base) - 1, minimo - 1, -1):
        seq.append((campo_base, base[:tamanho]))

    vistos: set[tuple[str, str]] = set()
    saida: list[tuple[str, str]] = []
    for par in seq:
        if par in vistos:
            continue
        vistos.add(par)
        saida.append(par)
        if len(saida) >= limite:
            break
    return saida


def pontuar(termo: str, descricao: str) -> float:
    """Nota de quanto a descricao casa com o termo (0.0 a 1.0)."""
    t = normalizar(termo)
    d = normalizar(descricao)
    if not t or not d:
        return 0.0
    if t == d:
        return 1.0
    if d.startswith(t):
        return 0.8
    if t.startswith(d):
        return 0.7
    return 0.0


def _termos_codigo(termo: str) -> list[str]:
    """Termos que podem casar com a COLUNA DE CODIGO da grade.

    '30010 - MARINAV' -> ['30010'] (o nome e a parte depois do separador).
    'BRIOS' -> ['BRIOS'] (palavra unica: pode ser codigo de porto).
    'AMELIA NAVIGATION' -> [] (nome com espaco nao e codigo).
    """
    bruto = str(termo or "").strip()
    saida: list[str] = []
    achado = _SEPARADORES.match(bruto)
    if achado and achado.group(1) != bruto:
        saida.append(achado.group(1))
    if " " not in bruto and bruto:
        saida.append(bruto)
    return saida


def _celula(linha: list[str], indice: int) -> str:
    if 0 <= indice < len(linha):
        return str(linha[indice]).strip()
    return ""


def escolher(termo: str, linhas: list[list[str]],
             campo: CampoLookup) -> tuple[int | None, list[dict]]:
    """Escolhe a linha da grade que casa com o termo.

    Casa pela descricao E pelo codigo: a ficha do agente vem com codigo em
    varios campos (porto 'BRIOS', agencia '30010'), e a grade traz o codigo
    na coluna 1.

    Devolve (indice_da_linha | None, candidatos). O indice e None quando nao
    ha resultado, quando o melhor casamento e fraco, ou quando dois cadastros
    empatam: nesses casos quem decide e quem opera.
    """
    if not linhas:
        return None, []

    termos_codigo = _termos_codigo(termo)
    pares: list[tuple[int, dict]] = []
    for indice, linha in enumerate(linhas):
        codigo = _celula(linha, campo.col_codigo)
        melhor_descricao, score_desc = "", -1.0
        for col in campo.cols_descricao:
            descricao = _celula(linha, col)
            score = pontuar(termo, descricao)
            if score > score_desc:
                melhor_descricao, score_desc = descricao, score
        melhor_score = max(score_desc, 0.0)
        for t in termos_codigo:
            score = pontuar(t, codigo)
            if score > melhor_score:
                melhor_score = score
        pares.append((indice, {
            "codigo": codigo,
            "descricao": melhor_descricao,
            "score": melhor_score,
        }))

    ordenados = sorted(pares, key=lambda p: -p[1]["score"])
    candidatos = [d for _, d in ordenados]
    melhor_score = ordenados[0][1]["score"]
    empatados = [p for p in ordenados if p[1]["score"] == melhor_score]
    if melhor_score < 0.7 or len(empatados) > 1:
        return None, candidatos
    return empatados[0][0], candidatos
