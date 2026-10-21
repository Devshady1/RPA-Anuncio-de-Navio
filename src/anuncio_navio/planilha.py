"""Leitura da planilha-modelo (modelo_anuncio_navio.xlsx) -> payload JSON da fila.

A planilha e lida pelos ROTULOS da coluna A (nao pela posicao da linha),
entao o usuario pode reordenar linhas sem quebrar o RPA. Listas suspensas
no formato "COD - Descricao" tem o codigo extraido automaticamente.

Uso:
    campos = ler_planilha("modelo_preenchida.xlsx")  # dict plano
    erros = validar_campos(campos)                   # [] se OK
    payload = construir_payload(campos)              # shape do payload da fila
"""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from anuncio_navio import config, tabelas

# A viagem nao vem da planilha (e sequencial, reservada via sequencia.proxima()
# no produtor); construir_payload mantem o campo porque o emissor sobrescreve.
VIAGEM_PADRAO = ""

# Rotulos de linha DUPLA (C = valor 1, D = valor 2).
DUPLOS = {
    "eta · chegada": ("eta_data", "eta_hora"),
    "etb · atracação": ("etb_data", "etb_hora"),
    "etb · atracacao": ("etb_data", "etb_hora"),
    "etc · conclusão": ("etc_data", "etc_hora"),
    "etc · conclusao": ("etc_data", "etc_hora"),
    "ets · saída": ("ets_data", "ets_hora"),
    "ets · saida": ("ets_data", "ets_hora"),
    "calado chegada (proa | popa)": ("calado_cheg_proa", "calado_cheg_popa"),
    "calado saída (proa | popa)": ("calado_sai_proa", "calado_sai_popa"),
    "calado saida (proa | popa)": ("calado_sai_proa", "calado_sai_popa"),
}
ROTULOS = {
    "nome do navio": "nome_navio",
    "imo": "imo",
    "imo (7 dígitos)": "imo",
    "imo (7 digitos)": "imo",
    "agência (código)": "agencia",
    "agencia (codigo)": "agencia",
    "agência (nome ou código)": "agencia",
    "agencia (nome ou codigo)": "agencia",
    "armador (código)": "armador",
    "armador (codigo)": "armador",
    "armador (nome ou código)": "armador",
    "armador (nome ou codigo)": "armador",
    "operador (código)": "operador",
    "operador (codigo)": "operador",
    "operador (nome ou código)": "operador",
    "operador (nome ou codigo)": "operador",
    "último porto (código)": "porto_ant",
    "ultimo porto (codigo)": "porto_ant",
    "último porto (nome ou código)": "porto_ant",
    "ultimo porto (nome ou codigo)": "porto_ant",
    "próximo porto (código)": "porto_prox",
    "proximo porto (codigo)": "porto_prox",
    "próximo porto (nome ou código)": "porto_prox",
    "proximo porto (nome ou codigo)": "porto_prox",
    "berço preferência": "berco",
    "berco preferencia": "berco",
    "afretador (código)": "afretador",
    "afretador (codigo)": "afretador",
    "afretador (nome ou código)": "afretador",
    "afretador (nome ou codigo)": "afretador",
    "eta data": "eta_data",
    "eta · data chegada": "eta_data",
    "eta hora": "eta_hora",
    "eta · hora chegada": "eta_hora",
    "etb data": "etb_data",
    "etb · data atracação": "etb_data",
    "etb · data atracacao": "etb_data",
    "etb hora": "etb_hora",
    "etb · hora atracação": "etb_hora",
    "etb · hora atracacao": "etb_hora",
    "etc data": "etc_data",
    "etc · data conclusão": "etc_data",
    "etc · data conclusao": "etc_data",
    "etc hora": "etc_hora",
    "etc · hora conclusão": "etc_hora",
    "etc · hora conclusao": "etc_hora",
    "ets data": "ets_data",
    "ets · data saída": "ets_data",
    "ets · data saida": "ets_data",
    "ets hora": "ets_hora",
    "ets · hora saída": "ets_hora",
    "ets · hora saida": "ets_hora",
    "tipo de viagem": "tipo_viagem",
    "tipo de operação": "tipo_operacao",
    "tipo de operacao": "tipo_operacao",
    "sentido": "sentido",
    "natureza": "natureza",
    "calado chegada proa": "calado_cheg_proa",
    "calado chegada · proa": "calado_cheg_proa",
    "calado chegada popa": "calado_cheg_popa",
    "calado chegada · popa": "calado_cheg_popa",
    "calado saída proa": "calado_sai_proa",
    "calado saida proa": "calado_sai_proa",
    "calado saída · proa": "calado_sai_proa",
    "calado saida · proa": "calado_sai_proa",
    "calado saída popa": "calado_sai_popa",
    "calado saida popa": "calado_sai_popa",
    "calado saída · popa": "calado_sai_popa",
    "calado saida · popa": "calado_sai_popa",
    "carga predominante (código)": "carga",
    "carga predominante (codigo)": "carga",
    "carga predominante (código 8 díg.)": "carga",
    "carga predominante (codigo 8 dig.)": "carga",
    "carga predominante (mercadoria)": "carga",
    "carga predominante (nome)": "carga",
    "carga predominante (nome da mercadoria)": "carga",
    "unidades (qtd_carga)": "qtd",
    "tons previstas": "tons",
    "loa / comprimento (m)": "loa",
    "tpb / dwt": "tpb",
}

OBRIGATORIOS = (
    "nome_navio", "imo", "agencia", "armador", "operador",
    "porto_ant", "porto_prox", "carga", "qtd", "loa",
    "eta_data", "eta_hora", "etb_data", "etb_hora",
    "etc_data", "etc_hora", "ets_data", "ets_hora",
    "tipo_viagem", "tipo_operacao", "sentido", "natureza",
    "calado_cheg_proa", "calado_cheg_popa", "calado_sai_proa", "calado_sai_popa",
)

CODIGOS_VALIDOS = {
    "tipo_viagem": {"1", "2", "3", "4", "5"},
    "tipo_operacao": {"1", "2", "4", "5", "6", "7", "8", "10", "11"},
    "sentido": {"1", "2", "3"},
    "natureza": {"1", "2", "3", "4", "5", "6"},
}

# Calado maximo aceito pelo PORTO (regra operacional de 13/10/2026: o porto
# opera com calados de ate 16 m). Nao confundir com o calado maximo DO NAVIO:
# um navio com calado maximo menor continua exigindo conferencia manual
# (ex.: TI SUNRISE, 10,527 m no summer) - aqui o teto do porto so barra
# digitacao absurda, nao valida a embarcacao.
CALADO_MAX_M = 16.0


# Campos da planilha que aceitam NOME ou CODIGO, e a tabela correspondente.
# Carga entra aqui desde 14/10/2026: o agente maritimo informa o NOME da
# mercadoria e a resolucao nome -> codigo NCM passou a ser dever do RPA
# (tabelas.resolver_carga). A regra que segue intacta: a carga NUNCA e
# adivinhada - nome ambiguo barra com os candidatos para escolha humana.
CAMPOS_CLASSIF = ("tipo_viagem", "tipo_operacao", "sentido", "natureza")

ROTULOS_CARGA = {
    "carga predominante (código)": "carga",
    "carga predominante (codigo)": "carga",
    "carga predominante (código 8 díg.)": "carga",
    "carga predominante (codigo 8 dig.)": "carga",
    "carga predominante (mercadoria)": "carga",
    "carga predominante (nome)": "carga",
    "carga predominante (nome da mercadoria)": "carga",
}

CAMPOS_RESOLVEIS = {
    "agência (nome ou código)": "agencia",
    "agencia (nome ou codigo)": "agencia",
    "agência (código)": "agencia",
    "agencia (codigo)": "agencia",
    "armador (nome ou código)": "armador",
    "armador (nome ou codigo)": "armador",
    "armador (código)": "armador",
    "armador (codigo)": "armador",
    # afretador: o agente escreve o NOME; o codigo sai da mesma base de armadores.
    "afretador (nome ou código)": "afretador",
    "afretador (nome ou codigo)": "afretador",
    "afretador (código)": "afretador",
    "afretador (codigo)": "afretador",
    "operador (nome ou código)": "operador",
    "operador (nome ou codigo)": "operador",
    "operador (código)": "operador",
    "operador (codigo)": "operador",
    "último porto (nome ou código)": "porto_ant",
    "ultimo porto (nome ou codigo)": "porto_ant",
    "último porto (código)": "porto_ant",
    "ultimo porto (codigo)": "porto_ant",
    "próximo porto (nome ou código)": "porto_prox",
    "proximo porto (nome ou codigo)": "porto_prox",
    "próximo porto (código)": "porto_prox",
    "proximo porto (codigo)": "porto_prox",
}
_CHAVE_POR_ROTULO = CAMPOS_RESOLVEIS


def _normalizar_rotulo(txt: object) -> str:
    s = str(txt or "").strip().lower().rstrip("*").strip()
    return re.sub(r"\s+", " ", s)


def _texto(valor: object) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _extrair_codigo(valor: str) -> str:
    """'1 - LONGO CURSO' -> '1'; 'BRMCZ - Maceio' -> 'BRMCZ'; '30010' -> '30010'."""
    v = valor.strip()
    m = re.match(r"^([A-Za-z0-9]+)\s*[-–—:]", v)
    return m.group(1) if m else v


def _resolver_classif(campo: str, valor: str) -> str:
    """'LONGO CURSO' -> '1'; '1' -> '1'; '1 - LONGO CURSO' -> '1'."""
    v = _extrair_codigo(valor)
    validos = CODIGOS_VALIDOS.get(campo, set())
    if v in validos:
        return v
    from anuncio_navio import config
    opcoes = config.Config.from_env().opcoes.get(campo, {})
    for cod, desc in opcoes.items():
        if desc.strip().casefold() == valor.strip().casefold():
            return cod
        if desc.strip().casefold() == v.strip().casefold():
            return cod
    return v  # deixa validar_campos() acusar o codigo invalido


def ler_planilha(path: str | Path, aba: str = "Anúncio") -> dict:
    """Le a planilha-modelo e retorna dict plano {chave: valor_str}."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Planilha nao encontrada: {p}")
    # read_only=True deixa o handle do arquivo aberto: no Windows isso travava a
    # planilha e impedia arquiva-la depois da leitura (inserir.py).
    wb = load_workbook(p, data_only=True, read_only=True)
    try:
        return _ler_aba(wb, aba, p)
    finally:
        wb.close()


def _ler_aba(wb, aba: str, p: Path) -> dict:
    if aba not in wb.sheetnames:
        raise ValueError(f"Aba '{aba}' nao encontrada (abas: {wb.sheetnames})")
    ws = wb[aba]
    campos: dict[str, str] = {}
    for linha in ws.iter_rows(min_row=2, max_col=4, values_only=True):
        rotulo = linha[0]
        v1 = linha[2] if len(linha) > 2 else None
        v2 = linha[3] if len(linha) > 3 else None
        norm = _normalizar_rotulo(rotulo)
        if norm in DUPLOS:
            k1, k2 = DUPLOS[norm]
            campos[k1] = _texto(v1)
            campos[k2] = _texto(v2)
            continue

        # Carga: o agente escreve o NOME da mercadoria e o RPA resolve o codigo
        # NCM. Nome ambiguo NAO e adivinhado: barra com os candidatos.
        if norm in ROTULOS_CARGA and (val := _texto(v1)):
            codigo, candidatos = tabelas.resolver_carga(val)
            if codigo:
                campos["carga"] = codigo
                continue
            opcoes = "\n  ".join(f"{c} - {d}" for c, d in candidatos[:6])
            raise ValueError(
                f"Mercadoria '{val}' nao pode ser resolvida sozinha.\n"
                + (f"  Possiveis:\n  {opcoes}\n"
                   if candidatos else
                   "  Nao encontrada na tabela de mercadorias (cargas.csv)."))
        # Resolve NOME -> CODIGO como no formulario de entrada. Sem isso o
        # agente teria que procurar o codigo na aba Catalogo, que e exatamente
        # o trabalho manual que a interface nova tenta eliminar.
        if norm in CAMPOS_RESOLVEIS and (val := _texto(v1)):
            codigo, alternativas = tabelas.resolver(_CHAVE_POR_ROTULO[norm], val)
            if codigo:
                campos[ROTULOS[norm]] = codigo
                continue
            opcoes = " · ".join(f"{c} ({d[:28]})" for c, d in alternativas)
            raise ValueError(
                f"'{val}' nao consta na tabela de {norm}. "
                + (f"Opcoes: {opcoes}" if opcoes else "Confira a digitacao.")
            )
        chave = ROTULOS.get(norm)
        if chave:
            campos[chave] = _texto(v1)
    faltando_colunas = [c for c in
                         ("nome_navio", "imo", "eta_data", "carga")
                         if c not in campos]
    if faltando_colunas:
        raise ValueError("Planilha fora do modelo: rotulos nao reconhecidos "
                         f"(ex.: {faltando_colunas}). Use ficha_anuncio_navio.xlsx.")
    for k in ("tipo_viagem", "tipo_operacao", "sentido", "natureza"):
        if campos.get(k):
            campos[k] = _resolver_classif(k, campos[k])
    # Classificacao nao e mais perguntada na ficha: vale o padrao 1/1/1/1
    # (longo curso / movimentacao de carga / exportacao / solido). Correcao
    # manual quando a operacao for diferente.
    config.aplicar_classificacao_padrao(campos)
    for k in ("agencia", "armador", "operador", "porto_ant", "porto_prox",
                "berco", "afretador", "carga"):
        if campos.get(k):
            campos[k] = _extrair_codigo(campos[k])
    return campos


def validar_campos(c: dict) -> list[str]:
    """Valida regras do OpenPort. Retorna lista de erros ([] = OK)."""
    erros = []
    for k in OBRIGATORIOS:
        if not (c.get(k) or "").strip():
            erros.append(f"Campo obrigatorio vazio: {k}.")
    if c.get("imo") and not re.fullmatch(r"\d{7}", c["imo"].strip()):
        erros.append("IMO deve ter exatamente 7 dígitos numéricos.")
    for k in ("eta_data", "etb_data", "etc_data", "ets_data"):
        v = (c.get(k) or "").strip()
        if v and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", v):
            erros.append(f"{k} fora do formato DD/MM/AAAA: '{v}'.")
    for k in ("eta_hora", "etb_hora", "etc_hora", "ets_hora"):
        v = (c.get(k) or "").strip()
        if v and not re.fullmatch(r"\d{2}:\d{2}", v):
            erros.append(f"{k} fora do formato HH:MM: '{v}'.")
    for k in ("calado_cheg_proa", "calado_cheg_popa", "calado_sai_proa", "calado_sai_popa"):
        v = (c.get(k) or "").strip().replace(",", ".")
        try:
            f = float(v) if v else 0.0
        except ValueError:
            erros.append(f"{k} deve ser numerico: '{v}'.")
            continue
        if v and (f <= 0 or f > CALADO_MAX_M):
            erros.append(f"{k} deve estar entre 0 e {CALADO_MAX_M:g} m: '{v}'.")
    for k, validos in CODIGOS_VALIDOS.items():
        v = (c.get(k) or "").strip()
        if v and v not in validos:
            erros.append(f"{k} com codigo invalido: '{v}'.")
    for k in ("loa",):
        v = (c.get(k) or "").strip().replace(",", ".")
        try:
            if v and float(v) <= 0:
                erros.append(f"{k} deve ser maior que zero.")
        except ValueError:
            erros.append(f"{k} deve ser numerico: '{v}'.")
    return erros


def construir_payload(c: dict) -> dict:
    """Monta o payload no mesmo shape do app.montar_payload()."""
    g = lambda k: (c.get(k) or "").strip()  # noqa: E731
    cal = lambda k: g(k).replace(",", ".")  # noqa: E731
    return {
        "nome_navio": g("nome_navio"),
        "imo": g("imo"),
        "agencia": g("agencia"),
        "armador": g("armador"),
        "operador": g("operador"),
        "porto_ant": g("porto_ant"),
        "porto_prox": g("porto_prox"),
        "berco": g("berco"),
        "afretador": g("afretador"),
        "eta": f"{g('eta_data')} {g('eta_hora')}".strip(),
        "etb": f"{g('etb_data')} {g('etb_hora')}".strip(),
        "etc": f"{g('etc_data')} {g('etc_hora')}".strip(),
        "ets": f"{g('ets_data')} {g('ets_hora')}".strip(),
        "carga": g("carga"),
        "qtd": g("qtd"),
        "tons": g("tons"),
        "calado": {
            "chegada_proa": cal("calado_cheg_proa"),
            "chegada_popa": cal("calado_cheg_popa"),
            "saida_proa": cal("calado_sai_proa"),
            "saida_popa": cal("calado_sai_popa"),
        },
        "loa": g("loa").replace(",", "."),
        "tpb": g("tpb").replace(",", "."),
        "documentos": {"dpem": "", "manifesto": "", "tripulantes": ""},
        "viagem": VIAGEM_PADRAO,
        "tipo_viagem": g("tipo_viagem"),
        "tipo_operacao": g("tipo_operacao"),
        "sentido": g("sentido"),
        "natureza": g("natureza"),
    }
