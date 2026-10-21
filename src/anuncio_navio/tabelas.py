"""Validacao de codigos sensiveis contra tabelas de referencia (CSV em tabelas/).

Cada CSV tem colunas: codigo,descricao. Ex.: agencias.csv, portos.csv,
cargas.csv, armadores.csv, operadores.csv.

- Tabela ausente -> validacao desse campo e pulada (fail-open documentado).
- Codigo inexistente -> erro + sugestao aproximada (difflib).
- Para expandir: pecaofficial a CODEBA ou raspagem unica das telas de
  consulta do QAS (somente leitura).
"""
from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TABELAS_DIR = ROOT / "tabelas"

# campo do payload -> arquivo CSV
MAPA = {
    "agencia": "agencias.csv",
    "armador": "armadores.csv",
    # afretador usa a mesma base de armadores (mesmo cadastro no OpenPort).
    # Sem esta entrada, _carregar("") tentava abrir a PASTA tabelas/ e quebrava
    # com PermissionError no lugar de resolver nome -> codigo.
    "afretador": "armadores.csv",
    "operador": "operadores.csv",
    "porto_ant": "portos.csv",
    "porto_prox": "portos.csv",
    "carga": "cargas.csv",
}


@lru_cache(maxsize=None)
def _carregar(nome_arquivo: str) -> dict:
    """Retorna {codigo_upper: descricao}. {} se arquivo ausente."""
    p = TABELAS_DIR / nome_arquivo
    if not p.exists():
        return {}
    dados = {}
    with p.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cod = (row.get("codigo") or "").strip().upper()
            if cod:
                dados[cod] = (row.get("descricao") or "").strip()
    return dados


def tabelas_disponiveis() -> list[str]:
    return sorted(p.name for p in TABELAS_DIR.glob("*.csv")) if TABELAS_DIR.exists() else []


def avisos_codigos(campos: dict, estrito: bool = False) -> list[str]:
    """Confere campos sensiveis contra as tabelas.

    Tabelas ainda incompletas -> retorna AVISOS (nao bloqueia) por padrao.
    Com estrito=True, codigo ausente em tabela existente vira erro bloqueante
    (use quando as tabelas estiverem completas).
    Tabela ausente -> campo pulado (fail-open documentado).
    """
    msgs = []
    for campo, arquivo in MAPA.items():
        valor = (campos.get(campo) or "").strip()
        if not valor:
            continue  # vazio e tratado pela validacao de obrigatoriedade
        tabela = _carregar(arquivo)
        if not tabela:
            continue  # sem referencia: nao bloqueia
        if valor.upper() in tabela:
            continue
        sug = difflib.get_close_matches(valor.upper(), tabela.keys(), n=3, cutoff=0.6)
        dica = f" Quis dizer: {', '.join(sug)}?" if sug else ""
        prefixo = "BLOQUEIO" if estrito else "Atenção"
        msgs.append(f"{prefixo}: {campo}='{valor}' nao consta em {arquivo}.{dica}")
    return msgs


# Alias de compatibilidade
def validar_codigos(campos: dict) -> list[str]:
    return avisos_codigos(campos, estrito=False)


def descricao(campo: str, codigo: str) -> str:
    """Descricao do codigo, ou '' se desconhecido."""
    return _carregar(MAPA.get(campo, "")).get((codigo or "").strip().upper(), "")


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c)).casefold()


# Palavras sem valor na comparacao de mercadoria (a NCM usa muitas delas).
_STOP_TOKENS = frozenset({
    "de", "da", "do", "das", "dos", "e", "ou", "com", "sem", "para", "pra",
    "em", "na", "no", "nas", "nos", "a", "o", "as", "os", "outro", "outra",
    "outros", "outras", "nao", "sim", "seu", "sua", "seus", "suas", "mais",
    "s", "n", "não", "até", "ate",
})

# Marcas de MERCADORIA-bruta/minerio na descricao da NCM. Navio opera com isso:
# sulfato, catalisador, residuo e desperdicio sao saida de balanca/outro processo
# eNAO entram no anuncio de navio (regra de dominio informada pelo usuario).
_TOKENS_MINERIO = frozenset({"MINERIO", "CONCENTRADO", "BRUTO", "AGRANEL", "GRANEL"})

# Residuo/desperdicio/refugo: saida de balanca e outros processos. O usuario
# confirmou em 14/10/2026 que navio NUNCA opera com isso, entao o RPA se recusa
# a devolver esses codigos (ex.: 18020000, cascas/peliculas de cacau). Se so
# existir codigo de residuo para o termo, a mercadoria nao resolve.
_TOKENS_DESPERDICIO = frozenset({"RESIDUO", "DESPERDICIO", "SUCATA", "REFUGO",
                                 "REJEITO", "BORRA", "CASCALHO", "PELICULA"})


def _tokens(s: str) -> frozenset:
    """Palavras uteis do texto: sem acento, sem pontuacao, sem plural.

    'MINERIOS DE NIQUEL E SEUS CONCENTRADOS' -> {'MINERIO', 'NIQUEL', 'CONCENTRADO'}.
    Assim 'minério de níquel' casa com a descricao mesmo no plural.
    """
    t = _sem_acento(s).upper()
    t = re.sub(r"[^A-Z0-9]+", " ", t)
    saida = set()
    for tok in t.split():
        if tok in _STOP_TOKENS:
            continue
        if len(tok) > 3 and tok.endswith("S"):
            tok = tok[:-1]
        if tok and tok not in _STOP_TOKENS:
            saida.add(tok)
    return frozenset(saida)


# Apelidos comerciais -> termo de busca na NCM (sob demanda). A NCM descreve o
# produto pela nomenclatura oficial e varias palavras do dia a dia do porto nao
# existem nela: 'amendoa de cacau' nao aparece em 18010000, que a NCM chama de
# 'CACAU INTEIRO OU PARTIDO,EM BRUTO OU TORRADO'. Sem isto o RPA diria 'nao
# encontrada' para mercadoria que opera todo dia.
APELIDOS_CARGA = {
    "amendoa de cacau": "cacau",
    "cacau em amendoa": "cacau",
    "grao de cacau": "cacau",
    "cacau em grao": "cacau",
}
_APELIDOS_TOKENS = {frozenset(_tokens(k)): v for k, v in APELIDOS_CARGA.items()}

# Codigo fixo confirmado pelo usuario (14/10/2026): quando chega CACAU, sempre
# 18010000 - 'CACAU INTEIRO OU PARTIDO,EM BRUTO OU TORRADO'. Nao existe codigo
# de 'amendoa': 'amendoa de cacau' e como o porto chama essa mesma mercadoria.
CODIGO_FIXO_CARGA = {
    "cacau": "18010000",
    "amendoa de cacau": "18010000",
    "cacau em amendoa": "18010000",
    "cacau em grao": "18010000",
    "grao de cacau": "18010000",
}
_CODIGO_FIXO_TOKENS = {frozenset(_tokens(k)): v for k, v in CODIGO_FIXO_CARGA.items()}


def _e_desperdicio(desc: str) -> bool:
    """True se a descricao da NCM e de residuo/desperdicio/refugo."""
    toks = _tokens(desc)
    if _TOKENS_DESPERDICIO & toks:
        return True
    return "DESPERDICIO" in _sem_acento(desc).upper()


def resolver_carga(texto: str) -> tuple[str, list[tuple[str, str]]]:
    """Resolve o NOME da mercadoria para o codigo NCM de 8 digitos.

    Decisao de 14/10/2026: o agente maritimo informa o NOME da mercadoria
    ('niquel') e a resolucao passou a ser dever do RPA. Regras de dominio do
    negocio, informadas pelo usuario:

      * navio carrega MERCADORIA, nunca residuo/desperdicio/refugo nem derivado
        quimico. Codigos de RESIDUOS/DESPERDICIOS, SULFATO, CATALISADOR etc. sao
        de saida de balanca e nao entram no anuncio - o RPA se recusa a devolver;
      * quando o mesmo nome bate em varios codigos, o RPA **prefere o minerio**
        (descricao com MINERIO/CONCENTRADO/BRUTO) e so resolve sozinho se
        sobrar UM. Se sobrarem varios que nao sejam minerio, devolve os
        candidatos para escolha humana - a carga nunca e adivinhada.

    Devolve (codigo, candidatos). codigo == '' quando nao encontra ou quando
    ficou ambiguo - ai os candidatos alimentam o erro/aviso.
    """
    tabela = _carregar(MAPA.get("carga", ""))
    t = (texto or "").strip()
    if not tabela or not t:
        return "", []

    if re.fullmatch(r"\d{8}", t) and t in tabela:
        if _e_desperdicio(tabela[t]):
            return "", []   # codigo de residuo: o RPA se recusa a devolver
        return t, []

    alvo = _tokens(t)
    if not alvo:
        return "", []

    # Codigo fixo confirmado pelo usuario: cacau e sempre 18010000.
    if alvo in _CODIGO_FIXO_TOKENS:
        return _CODIGO_FIXO_TOKENS[alvo], []

    # Apelido comercial conhecido: busca pelo termo que a NCM usa.
    if alvo in _APELIDOS_TOKENS:
        alvo = _tokens(_APELIDOS_TOKENS[alvo])

    uteis = {c: d for c, d in tabela.items() if not _e_desperdicio(d)}
    for cod, desc in uteis.items():
        if _tokens(desc) == alvo:
            return cod, []

    cands = [(cod, desc) for cod, desc in uteis.items() if alvo <= _tokens(desc)]
    if not cands:
        return "", []
    cands.sort(key=lambda x: (len(_tokens(x[1])), x[0]))

    # Prefere minerio/bruto: navio nao opera com sulfato, catalisador, residuo.
    minerio = [x for x in cands if _TOKENS_MINERIO & _tokens(x[1])]
    escolha = minerio or cands
    if len(escolha) == 1:
        return escolha[0][0], []
    return "", escolha[:12]


def _chave(s: str) -> str:
    """Normaliza p/ comparar: sem acento, sem case, sem espaco/pontuacao.

    Faz 'SEA LANES' == 'sealanes' e 'Ilheús' == 'ilheus'. Assim o agente pode
    digitar do jeito que conhece e ainda casar com a descricao da tabela.
    """
    t = _sem_acento(s)
    for ch in (" ", "-", ".", "/", "&", "'"):
        t = t.replace(ch, "")
    return t


def listar(campo: str) -> list[tuple[str, str]]:
    """Todos os (codigo, descricao) do campo, ordenados. [] se tabela ausente."""
    return sorted(_carregar(MAPA.get(campo, "")).items())


def buscar(campo: str, termo: str, limite: int = 20) -> list[tuple[str, str]]:
    """Autocomplete: codigo que começa com o termo OU descricao que contém.

    Busca sem acento e sem case. Retorna até `limite` pares (codigo, descricao).
    """
    t = _sem_acento((termo or "").strip())
    if len(t) < 2:
        return []
    achados = []
    for cod, desc in _carregar(MAPA.get(campo, "")).items():
        if _sem_acento(cod).startswith(t) or t in _sem_acento(desc):
            achados.append((cod, desc))
    achados.sort(key=lambda x: (not x[0].startswith("BR"), x[0]))
    return achados[:limite]


def resolver(campo: str, texto: str, corte: float = 0.80) -> tuple[str, list[tuple[str, str]]]:
    """Resolve o que o agente digitou (nome OU codigo) contra a tabela do campo.

    Devolve (codigo, alternativas). `codigo` e "" quando nao resolveu com
    confianca. `alternativas` alimenta a mensagem de erro na tela.

    Estrategia, do mais forte pro mais fraco:
      1. codigo exato
      2. descricao exatamente igual (ignorando acento, case, espaco)
      3. descricao contendo o termo, ou codigo comecando com o termo
      4. aproximacao por difflib sobre a chave normalizada (so acima do corte)

    O passo 4 NUNCA e acionado por calado ou carga: esses nao tem descricao
    unica e corrigir sozinho manda o navio para o porto errado. Para os dois
    o erro volta com as opcoes para o agente escolher.
    """
    t = (texto or "").strip()
    if not t:
        return "", []

    # 0) formato "CODIGO - Descricao" (vem de copiar de planilha/dropdown)
    m = re.match(r"^([A-Za-z0-9]+)\s*[-–—:]", t)
    if m and m.group(1).upper() in _carregar(MAPA.get(campo, "")):
        return m.group(1).upper(), []

    # 1) codigo exato
    if t.upper() in _carregar(MAPA.get(campo, "")):
        return t.upper(), []

    tabela = _carregar(MAPA.get(campo, ""))
    if not tabela:
        return "", []

    kt = _chave(t)

    # Carga: SO codigo exato pode ser assumido. Mercadoria nao tem descricao
    # unica e um prefixo ("2604000" -> "26040000") e exatamente o tipo de
    # palpite que anuncia a carga errada. Qualquer outra coisa vira opcao.
    if campo == "carga":
        candidatos = [(c, d) for c, d in tabela.items()
                      if _sem_acento(c).startswith(_sem_acento(t)) or kt in _chave(d)]
        return "", candidatos[:5]

    # 2) descricao exatamente igual (normalizada)
    for cod, desc in tabela.items():
        if desc and _chave(desc) == kt:
            return cod, []

    # 3) prefixo no codigo ou contido na descricao
    parciais = [(cod, desc) for cod, desc in tabela.items()
                if _sem_acento(cod).startswith(_sem_acento(t)) or kt in _chave(desc)]
    if len(parciais) == 1:
        return parciais[0][0], []
    if parciais:
        return "", parciais[:5]

    # 4) aproximacao por difflib
    if not kt:
        return "", []

    melhor: list[tuple[float, tuple[str, str]]] = []
    for cod, desc in tabela.items():
        for alvo in (desc, cod):
            if not alvo:
                continue
            r = difflib.SequenceMatcher(None, kt, _chave(alvo)).ratio()
            melhor.append((r, (cod, desc)))
    melhor.sort(key=lambda x: x[0], reverse=True)
    candidatos = [(c, d) for r, (c, d) in melhor if r >= corte]
    # descarta candidatos que sejam quase o mesmo item
    unicos: list[tuple[str, str]] = []
    for c, d in candidatos:
        if _chave(d) != _chave(t) and all(c != u[0] for u in unicos):
            unicos.append((c, d))
    if len(unicos) == 1:
        return unicos[0][0], []
    return "", unicos[:3]


@lru_cache(maxsize=None)
def _carregar_navios() -> list[dict]:
    """Linhas de navios.csv: imo, nome, especialidade, loa. [] se ausente."""
    p = TABELAS_DIR / "navios.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def buscar_navio(termo: str, limite: int = 20) -> list[dict]:
    """Autocomplete de navio por IMO (começa com) ou nome (contém)."""
    t = _sem_acento((termo or "").strip())
    if len(t) < 2:
        return []
    achados = []
    for n in _carregar_navios():
        imo = _sem_acento(n.get("imo", ""))
        nome = _sem_acento(n.get("nome", ""))
        if imo.startswith(t) or t in nome:
            achados.append(n)
    achados.sort(key=lambda n: (not _sem_acento(n.get("imo", "")).startswith(t),
                                _sem_acento(n.get("nome", ""))))
    return achados[:limite]


def rotulo_navio(n: dict) -> str:
    """'9553256 - VOYAGER | GRANELEIRO | LOA 190,00' (p/ selectbox)."""
    imo = (n.get("imo") or "").strip() or "s/IMO"
    base = f"{imo} - {(n.get('nome') or '').strip()}"
    esp = (n.get("especialidade") or "").strip()
    loa = (n.get("loa") or "").strip()
    if esp:
        base += f" | {esp}"
    if loa:
        base += f" | LOA {loa}"
    return base
