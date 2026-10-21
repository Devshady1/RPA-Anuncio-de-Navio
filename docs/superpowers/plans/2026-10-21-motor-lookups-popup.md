# Motor de Lookups pelo Popup do OpenPort — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** os 8 campos de classificação do anúncio (agência, portos, armador, afretador, berço, operador, tipo de mercadoria) passam a ser resolvidos pelo popup "Localizar" do próprio OpenPort, a partir do **nome** que o operador escreveu na planilha, sem depender de tabelas CSV locais.

**Architecture:** um módulo novo e puro (`lookup_engine.py`) decide *qual* linha escolher e *quais* buscas fazer; a camada de navegador (`browser.py`) executa a busca no popup e clica no link de seleção; `anuncio.py` orquestra os 8 campos com fallback para o caminho atual (digitar código + TAB). As tabelas CSV passam a ser fallback offline, não a fonte primária.

**Tech Stack:** Python 3 (stdlib `unittest`, sem pytest), Playwright 1.49.1, `openpyxl` só onde já é usado, macOS/Windows portáveis.

**Spec:** `docs/superpowers/specs/2026-10-21-entrega-macos.md` — seção 5 (motor de lookups), seção 5.6 (defeitos a corrigir). O plano implementa **apenas a Fase 1** da seção 9.

## Global Constraints

- Ambiente de teste: `python -m unittest discover -s tests` (stdlib, sem pytest). Idioma do código: **português**, identificadores sem acento, mensagens de log em ASCII (sem acento) porque os logs são lidos em terminal Windows.
- **PROD nunca é exercitado por teste.** Todo teste que abre navegador exige `RUN_QAS_TESTS=1` e `self.assertIn("/qas/", cfg.url)`; se a URL não for QAS, o teste falha (não pula).
- Nenhum teste pode acionar `GRAVAR`, `CONFIRMAR`, `VERIFICAR`, `EXCLUIR`, `SALVAR` na 2003. O bloqueio é feito por monkeypatch de `browser.acionar` nos testes de integração.
- Um commit por tarefa. Títulos no formato `feat:`, `fix:`, `test:`, `chore:`.
- Não alterar a semântica de `PERMITIR_PROD` / `CONFIRMAR_ANUNCIO` em `run.py`.
- Não renomear/mover `src/anuncio_navio/tabelas.py` nem `tabelas/*.csv`: são o fallback e a base dos testes existentes.
- A busca no popup é **prefixo**, **insensível a maiúsculas** e **sensível a acento**. Portanto o texto enviado ao popup **preserva os acentos** como o operador escreveu.
- Nenhum commit pode conter a senha do OpenPort, `.env` real ou dados de navegação de terceiros. `.env` já está no `.gitignore` — confirmar antes do primeiro commit.

## Review Focus

- O operador escreve `Ilhéus` (com acento) → o popup só encontra `Ilhéus`; se o acento for perdido no caminho, o porto não resolve e o anúncio não grava.
- O operador escreve `30010 - MARINAV` (código + nome, formato aceito hoje pela ficha) → o motor tem que extrair o código e usar o filtro de código, não o de descrição.
- O operador escreve `MARINAV LTDA` (nome com sufixo que não existe no cadastro) → o motor tem que degradar a busca até `MARINAV` e achar.
- Dois cadastros com o mesmo início (`AMELIA NAVIGATION` e `Amelia ship`) → o motor **não pode escolher um no chute**; tem que recusar e devolver os candidatos.
- O campo `carga` tem 6 colunas na grade e a descrição que o operador conhece é a **última** coluna (mercadoria completa), não a "Descrição Resumida" → a escolha do texto de comparação é diferente dos outros 7 campos.
- O popup de portos devolve 1.369 linhas para o prefixo "A" → a busca precisa de "sem paginação" marcada e de um prefixo mínimo, senão o clique vai para a linha errada.

---

### Task 0: Baseline — o "botão de voltar"

**Files:**
- Create: nenhum
- Modify: nenhum (o commit adiciona o estado atual)

**Interfaces:**
- Consumes: nada
- Produces: tag `v0.0.1-baseline` — ponto de retorno para qualquer task seguinte

- [ ] **Step 1: Confirmar que nada sensível vai entrar no commit**

Run:
```powershell
git status --porcelain
git check-ignore -v .env
```
Expected: `.env` aparece como ignorado (`git check-ignore` imprime a regra). Se `.env` **não** estiver ignorado, adicionar `.env` ao `.gitignore` antes de continuar.

- [ ] **Step 2: Verificar que os testes passam antes de congelar o estado**

Run: `python -m unittest discover -s tests`
Expected: `OK` (35 testes).

- [ ] **Step 3: Confirmar que a branch não tem commits**

Run: `git log --oneline`
Expected: `fatal: your current branch 'master' does not have any commits yet`

- [ ] **Step 4: Criar o commit inicial**

```powershell
git add -A
git commit -m "chore: baseline do RPA de anuncio de navio (24 rodadas QAS, 1 gravacao PROD)"
git tag v0.0.1-baseline
```

- [ ] **Step 5: Verificar**

Run: `git log --oneline; git tag`
Expected: 1 commit listando, e `v0.0.1-baseline` na lista de tags.

---

### Task 1: `lookup_engine.py` — decisões de busca (puro, sem navegador)

**Files:**
- Create: `src/anuncio_navio/lookup_engine.py`
- Test: `tests/test_lookup_engine.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `CampoLookup(chave: str, rotulo: str, seletor_visivel: str, seletor_hidden: str, seletor_lupa: str, filtro_descricao: str, filtro_codigo: str, col_codigo: int, cols_descricao: tuple[int, ...])` — dataclass congelada
  - `CAMPOS: tuple[CampoLookup, ...]` — os 8 campos, na ordem do Bloco 3 de `anuncio.py`
  - `normalizar(txt: str) -> str`
  - `consultas(termo: str, minimo: int = 4, limite: int = 6) -> list[tuple[str, str]]` — pares `(campo_filtro, termo)`, campo_filtro ∈ `{"descricao", "codigo"}`
  - `pontuar(termo: str, descricao: str) -> float`
  - `escolher(termo: str, linhas: list[list[str]], campo: CampoLookup) -> tuple[int | None, list[dict]]` — devolve `(índice_da_linha_chosen | None, candidatos)`

**Valores fixos de `CAMPOS`** (medidos no QAS em 21/10/2026 — spec seção 5.2). `col_codigo` é o índice da célula do código na grade (a célula 0 é o link de seleção); `cols_descricao` são os índices das células que podem conter o texto que o operador conhece:

| chave | rotulo | seletor_visivel | seletor_hidden | seletor_lupa | filtro_descricao | filtro_codigo | col_codigo | cols_descricao |
|---|---|---|---|---|---|---|---|---|
| porto_ant | PortoAnt | `#NUM_PORTO_ANT_2` | `#NUM_PORTO_ANT` | `#ANUM_PORTO_ANT` | `sqlFiltroDescricao` | `sqlCOD_PORTO` | 1 | (2,) |
| porto_prox | PortoProx | `#NUM_PORTO_PROX_2` | `#NUM_PORTO_PROX` | `#ANUM_PORTO_PROX` | `sqlFiltroDescricao` | `sqlCOD_PORTO` | 1 | (2,) |
| armador | Armador | `#NUM_ARMADOR_2` | `#NUM_ARMADOR` | `#ANUM_ARMADOR` | `sqlFiltroDescricao` | `sqlCOD_EMPRESA` | 1 | (2,) |
| afretador | Afretador | `#NUM_AFRETADOR_2` | `#NUM_AFRETADOR` | `#ANUM_AFRETADOR` | `sqlFiltroDescricao` | `sqlCOD_EMPRESA` | 1 | (2,) |
| agencia | Agencia | `#NUM_AGENCIA_2` | `#NUM_AGENCIA` | `#ANUM_AGENCIA` | `sqlNOM_FANTASIA` | `SqlCOD_EMPRESA` | 1 | (2,) |
| berco | Berco | `#NUM_BERCO_2` | `#NUM_BERCO` | `#ANUM_BERCO` | `sqlDCR_BERCO` | `sqlCOD_BERCO` | 1 | (2, 6) |
| operador | Operador | `#NUM_OPERADOR_2` | `#NUM_OPERADOR` | `#ANUM_OPERADOR` | `sqlFiltroDescricao` | `sqlCOD_EMPRESA` | 1 | (2,) |
| carga | Carga | `#NUM_TIP_MERCAD_2` | `#NUM_TIP_MERCAD` | `#ANUM_TIP_MERCAD` | `sqlDCR_TIP_MERCAD` | `sqlCOD_TIP_MERCAD` | 1 | (2, 6) |

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_lookup_engine.py` com o cabeçalho padrão do projeto (`sys.path.insert(0, str(ROOT / "src"))` onde `ROOT = Path(__file__).resolve().parent.parent`) e os testes:

```python
class TestNormalizar(unittest.TestCase):
    def test_remove_acento_e_maiuscula(self):
        self.assertEqual(lookup_engine.normalizar("Ilhéus"), "ILHEUS")

    def test_colapsa_espacos(self):
        self.assertEqual(lookup_engine.normalizar("  MARINAV   LTDA "), "MARINAV LTDA")


class TestConsultas(unittest.TestCase):
    def test_termo_simples_gera_prefixos_decrescentes(self):
        self.assertEqual(lookup_engine.consultas("MARINAV"),
                         [("descricao", "MARINAV"), ("descricao", "MARINA"),
                          ("descricao", "MARIN"), ("descricao", "MARI")])

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

    def test_sem_relacao_nao pontua(self):
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

    def test_carga_compara_com_a_mercadoria_completa(self):
        linhas = [["", "02061000", "MIUDEZAS COMESTIVEIS", "2",
                   "CARNES E MIUDEZAS, COMESTIVEIS.",
                   "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS"]]
        idx, _ = lookup_engine.escolher(
            "MIUDEZAS COMESTIVEIS DE BOVINO,FRESCAS OU REFRIGERADAS", linhas, self.carga)
        self.assertEqual(idx, 0)


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
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `python -m unittest tests.test_lookup_engine -v`
Expected: `ERROR: ModuleNotFoundError: No module named 'anuncio_navio.lookup_engine'`

- [ ] **Step 3: Implementar `src/anuncio_navio/lookup_engine.py`**

Cabeçalho e imports: `from __future__ import annotations`, `import re`, `import unicodedata`, `from dataclasses import dataclass`.

`normalizar(txt)`: NFD → remove caracteres combinantes (`unicodedata.combining`) → `re.sub(r"\s+", " ", s).strip().upper()`.

`consultas(termo, minimo=4, limite=6)`: monta a lista na ordem: `("descricao", termo)`; se o termo casar com `^([A-Za-z0-9]+)\s*[-–—:]` e o grupo 1 for diferente do termo inteiro, acrescenta `("codigo", grupo1)`; se o termo não tiver espaço, for alfanumérico e tiver 3 caracteres ou mais, acrescenta `("codigo", termo)`; se o termo tiver espaço, acrescenta `("descricao", termo sem a última palavra)`; depois, para a base (termo sem a última palavra, ou o termo), acrescenta os prefixos de tamanho `len(base)-1` até `minimo` inclusive. Deduplica preservando a ordem e corta em `limite`. A consulta de código nunca é tentada antes da de descrição com o mesmo texto, de modo que um nome que bate por descrição não gasta uma ida extra ao servidor.

`pontuar(termo, descricao)`: normaliza os dois; se forem iguais → `1.0`; se a descrição começar com o termo → `0.8`; se o termo começar com a descrição → `0.7`; senão `0.0`.

`escolher(termo, linhas, campo)`: para cada linha, extrai o código (`linha[campo.col_codigo]`) e a melhor descrição entre `campo.col_descricao` (índice mais válido da linha), calcula o `pontuar` e monta `{"codigo": ..., "descricao": ..., "score": ...}`. Devolve `(None, [])` se não houver linhas. Escolhe o índice de maior `score`; devolve `(None, candidatos)` se o melhor score for `< 0.7` **ou** se houver mais de um candidato com o mesmo melhor score; senão devolve `(índice, candidatos)`.

`CAMPOS`: a tupla com os 8 campos da tabela acima, exatamente com os valores fixados.

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `python -m unittest tests.test_lookup_engine -v`
Expected: todos `ok`.

- [ ] **Step 5: Rodar a suíte inteira (nada quebrou)**

Run: `python -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 6: Commit**

```powershell
git add src/anuncio_navio/lookup_engine.py tests/test_lookup_engine.py
git commit -m "feat: motor puro de decisao de lookups (normalizar, consultas, escolher)"
```

---

### Task 2: `browser.py` — busca no popup e seleção pelo link

**Files:**
- Modify: `src/anuncio_navio/browser.py` (adiciona `resolver_lookup_popup`; não remover `_resolver_via_lupa` ainda — vira fallback)
- Test: `tests/test_lookup_qas.py` (novo, opt-in por `RUN_QAS_TESTS=1`)

**Interfaces:**
- Consumes: `lookup_engine.CampoLookup`, `lookup_engine.consultas`, `lookup_engine.escolher`
- Produces:
  - `browser.resolver_lookup_popup(page: Page, campo: lookup_engine.CampoLookup, termo: str) -> tuple[bool, list[dict]]` — devolve `(resolvido, candidatos)`; `resolvido` é `True` quando o campo hidden ficou preenchido; `candidatos` é a lista de candidatos do último filtro que devolveu linhas (vazia quando resolveu)
  - `browser._popup_filtrar(popup: Page, campo: CampoLookup, campo_filtro: str, termo: str) -> list[list[str]]` — devolve as linhas da grade (`td` de cada `tr` com `td`), já com "sem paginação" marcada

- [ ] **Step 1: Escrever o teste de integração QAS que falha**

Criar `tests/test_lookup_qas.py`:

```python
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from anuncio_navio import browser, lookup_engine, navegacao
from anuncio_navio.config import Config, URL_QAS


@unittest.skipUnless(os.getenv("RUN_QAS_TESTS") == "1",
                     "definir RUN_QAS_TESTS=1 para rodar contra o QAS")
class TestLookupNoQas(unittest.TestCase):
    CASOS = [
        ("agencia", "MARINAV", "30010"),
        ("armador", "AMELIA NAVIGATION", "60700"),
        ("afretador", "AFRICAN TOUCAN SHIPPING CO", "0052025"),
        ("operador", "INTERMARIT", "30002"),
        ("berco", "BERÇO 101", "101"),
        ("porto_ant", "Ilhéus", "BRIOS"),
        ("carga", "MIUDEZAS COMESTIVEIS", "02061000"),
    ]

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.bw = cls.pw.chromium.launch(headless=True, slow_mo=0)
        cls.ctx = cls.bw.new_context(no_viewport=True)
        cls.ctx.set_default_timeout(20000)
        browser.ao_nova_pagina(cls.ctx)
        cls.page = cls.ctx.new_page()
        cfg = Config.from_env(url_override=URL_QAS)
        assert cfg.ambiente == "QAS", cfg.url
        cls.cfg = cfg
        navegacao.login(cls.page, cfg)
        navegacao.abrir_tela_2003(cls.page, cfg)
        navegacao.novo_registro(cls.page, cfg)

    @classmethod
    def tearDownClass(cls):
        for obj in ("ctx", "bw"):
            try:
                getattr(cls, obj).close()
            except Exception:
                pass
        try:
            cls.pw.stop()
        except Exception:
            pass

    def test_resolve_por_nome(self):
        for chave, termo, codigo_esperado in self.CASOS:
            campo = next(c for c in lookup_engine.CAMPOS if c.chave == chave)
            ok, cands = browser.resolver_lookup_popup(self.page, campo, termo)
            self.assertTrue(ok, f"{chave}: nao resolveu '{termo}' (candidatos={cands})")
            visivel = self.page.locator(campo.seletor_visivel).first.input_value().strip()
            self.assertEqual(visivel, codigo_esperado, f"{chave}: visivel='{visivel}'")
            hidden = self.page.locator(campo.seletor_hidden).first.input_value().strip()
            self.assertTrue(hidden, f"{chave}: hidden vazio")

    def test_filtro_traz_a_lista_inteira_sem_paginacao(self):
        # 'sem paginacao' desmarcada devolve a pagina 1; o prefixo 'A' no popup
        # de portos tem mais de mil linhas. Se a lista vier truncada, o indice
        # escolhido pela engine aponta para a linha errada.
        campo = next(c for c in lookup_engine.CAMPOS if c.chave == "porto_ant")
        with self.page.expect_popup(timeout=12000) as pi:
            self.page.locator(campo.seletor_lupa).first.evaluate("el => el.click()")
        popup = pi.value
        try:
            popup.set_default_timeout(15000)
            popup.wait_for_load_state("domcontentloaded")
            browser.esperar(popup, 2000)
            linhas = browser._popup_filtrar(popup, campo, "descricao", "A")
            self.assertGreater(len(linhas), 100, f"lista truncada: {len(linhas)}")
        finally:
            popup.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m unittest tests.test_lookup_qas -v`
Expected: `AttributeError: module 'anuncio_navio.browser' has no attribute 'resolver_lookup_popup'`

- [ ] **Step 3: Implementar `_popup_filtrar` e `resolver_lookup_popup` em `browser.py`**

`_popup_filtrar(popup, campo, campo_filtro, termo)`:
1. marca a caixa "sem paginação" (`popup.locator("input[type=checkbox]").first`) se houver e não estiver marcada; espera 700 ms;
2. preenche `popup.locator("#" + (campo.filtro_descricao if campo_filtro == "descricao" else campo.filtro_codigo)).first` com `termo`;
3. clica `popup.locator("#BPESQUISAR").first` via `evaluate("el => el.click()")`;
4. espera 3 s e devolve `popup.evaluate` de uma lista com as linhas da grade: para cada `tr` de `table#TQuery` que tenha `td`, a lista de `td.innerText.trim()`.

`resolver_lookup_popup(page, campo, termo)`:
1. `botao = page.locator(campo.seletor_lupa).first`; se `count() == 0`, logar `"  {rotulo}: botao lupa nao localizado."` e devolver `(False, [])`;
2. abrir o popup com `page.expect_popup(timeout=12000)` e `botao.evaluate("el => el.click()")`; em caso de timeout, logar e devolver `(False, [])`;
3. para cada `(campo_filtro, texto)` de `lookup_engine.consultas(termo)`:
   - `linhas = _popup_filtrar(popup, campo, campo_filtro, texto)`;
   - se `linhas` estiver vazia, continuar para a próxima consulta;
   - `idx, cands = lookup_engine.escolher(termo, linhas, campo)`;
   - se `idx is None`: guardar `cands` como candidatos e **continuar** para a próxima consulta (uma busca melhor pode resolver);
   - se `idx is not None`: clicar no link de seleção da linha `idx` — `popup.locator("table#TQuery tr a[onclick*='QueryValor']").nth(idx)` — via `evaluate("el => el.click()")`; esperar o popup fechar (`popup.wait_for_event("close", timeout=8000)`) e esperar 2 s na página principal; ler o valor do hidden com `page.locator(campo.seletor_hidden).first.input_value()`; se não estiver vazio, fechar o popup se ainda estiver aberto e devolver `(True, [])`; se estiver vazio, logar e devolver `(False, cands)`.
4. Se nenhuma consulta devolveu linhas, fechar o popup e devolver `(False, [])`.

Logs: usar `logger.info`/`logger.warning` com o rótulo e o termo, em ASCII (sem acento).

- [ ] **Step 4: Rodar o teste QAS e ver passar**

Run: `RUN_QAS_TESTS=1 python -m unittest tests.test_lookup_qas -v`
Expected: `ok` para os 7 casos. Se `porto_ant` falhar com "nao resolveu", conferir se o texto enviado foi `Ilhéus` com acento (a busca do popup é sensível a acento) — nunca trocar por `ILHEUS`.

- [ ] **Step 5: Rodar a suíte pura (o teste QAS é pulado sem a variável)**

Run: `python -m unittest discover -s tests`
Expected: `OK` (o teste QAS aparece como `skipped`).

- [ ] **Step 6: Commit**

```powershell
git add src/anuncio_navio/browser.py tests/test_lookup_qas.py
git commit -m "feat: resolver lookups pelo popup do OpenPort (busca por descricao e clique no link)"
```

---

### Task 3: `planilha.py` + `anuncio.py` — o Bloco 3 passa a usar o motor

**Files:**
- Modify: `src/anuncio_navio/planilha.py` (blocos `:256-284` e `:298-301`)
- Modify: `src/anuncio_navio/anuncio.py` (Bloco 3, `:60-88`)
- Test: `tests/test_planilha.py` (novos casos) e `tests/test_anuncio_lookup.py` (novo)

**Interfaces:**
- Consumes: `lookup_engine.CAMPOS`, `browser.resolver_lookup_popup`, `tabelas.resolver`, `tabelas.resolver_carga`
- Produces:
  - `planilha.ler_ficha(...)` passa a devolver, para os 8 campos de classificação, **o texto como o operador escreveu** em `campos[chave]` e, quando o CSV local conseguir resolver, o código em `campos[chave + "_codigo"]` (string vazia quando não resolve). **Nenhum `ValueError` é levantado por nome não resolvido** — a verdade do cadastro está no OpenPort.
  - `anuncio._campos_lookup(d: dict) -> list[tuple[lookup_engine.CampoLookup, str, str]]` — devolve `(campo, termo_bruto, codigo_fallback)` para os campos preenchidos, na ordem de `lookup_engine.CAMPOS`. Função pura, testável sem navegador.
  - `anuncio.criar_anuncio(...)` levanta `anuncio_navio.exceptions.LookupError` **antes** do Gravar quando um campo de classificação obrigatório não resolve, com a mensagem no formato `"{rotulo} '{termo}' nao encontrado no cadastro. Candidatos: {lista}"`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_planilha.py`, acrescentar:

```python
class TestLookupsPreservamTexto(unittest.TestCase):
    def test_nome_desconhecido_nao_derruba_a_ficha(self):
        # 'ZZZ EMPRESA QUE NAO EXISTE' nao esta no CSV local, mas pode existir
        # no OpenPort: a decisao final e do popup, nao da copia local.
        campos = planilha.ler_ficha(_ficha_com("armador (nome ou código)",
                                               "ZZZ EMPRESA QUE NAO EXISTE"))
        self.assertEqual(campos["armador"], "ZZZ EMPRESA QUE NAO EXISTE")
        self.assertEqual(campos.get("armador_codigo", ""), "")

    def test_nome_conhecido_guarda_o_codigo_como_fallback(self):
        campos = planilha.ler_ficha(_ficha_com("armador (nome ou código)", "MARINAV"))
        self.assertEqual(campos["armador"], "MARINAV")
        self.assertTrue(campos["armador_codigo"])
```

(ajustar `_ficha_com` ao helper que já existir no arquivo para montar uma ficha em memória; se não existir, criar uma que chame `planilha.ler_ficha` com um `.xlsx` temporário escrito por `openpyxl` com a aba `Anúncio` e os rótulos do modelo.)

Em `tests/test_anuncio_lookup.py` (novo):

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m unittest tests.test_planilha tests.test_anuncio_lookup -v`
Expected: `AttributeError: module 'anuncio_navio.anuncio' has no attribute '_campos_lookup'` e/ou falha nos casos de `planilha`.

- [ ] **Step 3: Ajustar `planilha.py`**

- No bloco de carga (`:256-268`): manter o texto bruto em `campos["carga"]` e gravar o código do CSV em `campos["carga_codigo"]` **sem** levantar `ValueError` quando não resolver. Não remover a chamada a `tabelas.resolver_carga` — ela é o fallback.
- No bloco `CAMPOS_RESOLVEIS` (`:269-281`): idem — `campos[chave] = texto bruto`, `campos[chave + "_codigo"] = codigo` (ou `""`).
- No bloco final (`:298-301`): aplicar `_extrair_codigo` apenas aos valores `*_codigo`, nunca ao texto bruto (o texto bruto preserva "30010 - MARINAV" para o motor extrair).
- Atualizar o comentário do bloco de carga: a ambiguidade passa a ser decidida no popup, e o CSV local vira fallback.

- [ ] **Step 4: Ajustar `anuncio.py`**

Adicionar:

```python
def _campos_lookup(d: dict) -> list[tuple["lookup_engine.CampoLookup", str, str]]:
    """Campos de classificação preenchidos: (campo, termo do operador, codigo fallback)."""
    saida = []
    for campo in lookup_engine.CAMPOS:
        termo = (d.get(campo.chave) or "").strip()
        if not termo:
            continue
        saida.append((campo, termo, (d.get(campo.chave + "_codigo") or "").strip()))
    return saida
```

E reescrever o Bloco 3 (`:60-88`) para:

```python
pend = []
for campo, termo, codigo_fallback in _campos_lookup(d):
    ok = browser.resolver_lookup_popup(page, campo, termo)
    if not ok and codigo_fallback:
        ok = browser.preencher_lookup(page, campo.seletor_visivel, campo.seletor_hidden,
                                      campo.seletor_lupa, codigo_fallback, campo.rotulo)
    if not ok:
        pend.append(f"{campo.rotulo}='{termo}'")
```

Se `pend` não estiver vazio, **levantar `LookupError`** antes do Bloco 4/Gravar, com a mensagem `"Lookups nao resolvidos: " + ", ".join(pend)` — o OpenPort só aceitaria recusar com "Armador Afretador não pode ficar vazio", que é mensagem de programador para o operador. Guardar a captura de tela com `browser.screenshot(page, config.project_root, "lookup_pendente")` antes de levantar.

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `python -m unittest tests.test_planilha tests.test_anuncio_lookup -v`
Expected: todos `ok`.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `python -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 7: Commit**

```powershell
git add src/anuncio_navio/planilha.py src/anuncio_navio/anuncio.py tests/test_planilha.py tests/test_anuncio_lookup.py
git commit -m "feat: Bloco 3 resolve lookups pelo popup e barra antes do Gravar"
```

---

### Task 4: Fluxo completo em QAS com nome (regressão do anúncio)

**Files:**
- Modify: nenhum previsto (só ajuste se o teste revelar defeito — nesse caso, um `fix:` separado)
- Test: `tests/test_anuncio_qas.py` (novo, opt-in por `RUN_QAS_TESTS=1`)

**Interfaces:**
- Consumes: `main.executar_um`, `fila_json`, `planilha`, `lookup_engine`
- Produces: prova de que uma ficha **com nomes** gera um anúncio completo no QAS, do começo ao fim

- [ ] **Step 1: Escrever o teste de fluxo completo**

Criar `tests/test_anuncio_qas.py` com `skipUnless(RUN_QAS_TESTS == "1")`, que:
1. exige `self.assertIn("/qas/", cfg.url)` e `self.assertNotIn("PERMITIR_PROD", os.environ)`;
2. monta um `dados` no formato de `fila_json.normalizar` com `imo` de um navio real do QAS, `viagem`, `agencia="MARINAV"`, `armador="AMELIA NAVIGATION"`, `operador="INTERMARIT"`, `porto_ant="Ilhéus"`, `porto_prox="Suape"`, `carga="02061000"` e as 4 datas/horas;
3. chama `main.executar_um(page, cfg, dados)` **bloqueando** as ações destrutivas: monkeypatch de `browser.acionar` para ignorar `btn_gravar`, `btn_confirmar`, `btn_verificar` (função que apenas registra o css acionado e não clica);
4. afirma que **nenhum** `LookupError` foi levantado e que os 6 campos de classificação ficaram preenchidos (hidden não vazio) depois do Bloco 3.

- [ ] **Step 2: Rodar e ver o resultado**

Run: `RUN_QAS_TESTS=1 python -m unittest tests.test_anuncio_qas -v`
Expected: `ok`. Se falhar, corrigir em commit próprio (`fix: ...`) antes de seguir.

- [ ] **Step 3: Rodar a suíte completa**

Run: `python -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 4: Commit**

```powershell
git add tests/test_anuncio_qas.py
git commit -m "test: fluxo completo de anuncio em QAS partindo de nomes"
```

---

### Task 5: Documentação

**Files:**
- Modify: `README.md` (seção de lookups: "os campos podem ser escritos por nome; a resolução é feita pelo OpenPort")
- Modify: `memory.md` (append da decisão: motor de lookups pelo popup, medidas em 21/10/2026, defeitos 5.6 corrigidos)

- [ ] **Step 1: Escrever a seção no `README.md`**

Explicar, em 5 a 8 linhas, que os 8 campos de classificação aceitam **nome ou código**, que a resolução é feita pelo popup do OpenPort (fonte viva) e que a tabela CSV local é fallback.

- [ ] **Step 2: Registrar no `memory.md`**

Append datado de 2026-10-21: o que o reconhecimento mediu (prefixo/case/acento, link de seleção, o que `QueryValor` grava), os 3 defeitos corrigidos e o fato de que as tabelas CSV viraram fallback.

- [ ] **Step 3: Commit**

```powershell
git add README.md memory.md
git commit -m "docs: lookups resolvidos pelo popup do OpenPort"
```

---

## Fora do escopo deste plano

Fases 2 a 5 da spec (entrega por planilha com `C3`/`HISTÓRICO`, instalador macOS com `launchd`, fila de pedidos + auto-update, automação de cadastro da CODEBA). Este plano entrega **a Fase 1**; as demais têm planos próprios quando forem implementadas.

## Handoff

Depois de Task 5, a Fase 1 está pronta para uso em QAS. **Não promover para PROD sem repetir a verificação de ids dos popups no PROD** (spec, risco 5) — os ids medidos valem para QAS; a verificação em PROD é leitura de tela, sem gravação.
