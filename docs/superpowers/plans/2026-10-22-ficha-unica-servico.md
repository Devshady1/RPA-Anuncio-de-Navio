# Ficha única e serviço invisível — Plano A (ciclo da ficha) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O agente preenche a única ficha da pasta `ficha/`, salva e fecha; o robô valida, anuncia, devolve o veredito na `C3`, arquiva a ficha preenchida e deixa uma nova em branco com o `HISTÓRICO` — sem terminal.

**Architecture:** Um ciclo puro (`servico.processar`) lê a ficha por cópia, usa o `planilha`/`fila_json`/`main` já validados, escreve o resultado com openpyxl e troca o arquivo atomicamente (`os.replace`). O `monitor_fila.py --servico` só repete o ciclo sob trava de instância única. O instalador (Plano B, separado) consome `caminhos`, `notificar`, `trava` e o modo `--servico`.

**Tech Stack:** Python 3.12, openpyxl, python-dotenv, Playwright (inalterado), unittest.

**Spec:** `docs/superpowers/specs/2026-10-22-entrega-macos-design.md` (seções 5, 6, 7, 8, 9)

## Global Constraints

- Testes rodam no Windows, offline, sem abrir browser; nunca anunciar em teste.
- Nenhuma dependência nova (openpyxl, python-dotenv, playwright, reportlab já existem).
- Layout de desenvolvimento (raiz do repo) continua igual: `run.py --fila`, `inserir.py` e o
  `monitor_fila.py` atual não podem mudar de comportamento; o modo novo é opt-in (`--servico`).
- Código e logs em ASCII (padrão do repo); textos que o agente lê (C3, notificação) em português
  com acentos, UTF-8.
- Nos testes, `MODELO = Path(__file__).resolve().parents[1] / "src" / "anuncio_navio" / "recursos" /
  "ficha_modelo.xlsx"` no topo do módulo (os trechos abaixo assumem esse nome).
- Estado fica em `data/` (`status.json`, `sequencia.json`, `estado_ficha.json`, `historico.csv`,
  `pedidos.csv`, `json/`); o JSON da fila continua no formato de `fila_json`.
- Regra de ouro da ficha: sucesso → arquiva e gera nova; falha → a mesma ficha fica, com o motivo
  na `C3`; nada se perde; a ficha parada não é reprocessada.
- Mensagens fixas (copiar verbatim nos testes):
  - inválida: `NÃO FOI ENVIADO — faltam 2 campo(s): IMO, CARGA. Corrija e salve de novo.`
  - pedido/lookup: `NÃO FOI ENVIADO — ` + mensagem do `LookupError` (que já traz os candidatos)
  - senha: `NÃO FOI ENVIADO — a senha do OpenPort mudou. Rode CONFIGURAR.command.`
  - outro erro: `NÃO FOI ENVIADO — ` + primeira linha do erro + `. A ficha foi mantida; salve de novo para tentar.`
  - notificação ok: `Anúncio <IMO> viagem <VIAGEM> gravado — DUV <DUV>.`
  - notificação duplicado: `Este navio já foi anunciado (DUV <DUV>). A ficha foi arquivada.`
  - notificação ocupada: `Feche a planilha para o robô processar.`
  - notificação falha: `NÃO FOI ENVIADO — veja a ficha (linha STATUS).`

## Review Focus

1. **Ficha re-salva (Excel antigo ainda aberto)** — o robô não pode anunciar o mesmo navio duas
   vezes: mesmo IMO + mesma ETA em `status.json` = duplicado. Teste na Task 8.
2. **Ficha aberta na hora do ciclo** — o robô espera e não escreve por cima do arquivo do agente.
   Teste na Task 6 (`esta_livre`) e Task 8 (`ocupada`).
3. **Datas/números digitados como célula de data/número no Excel** — não podem virar
   `2026-11-28 00:00:00` nem `1000.0`. Teste na Task 3.
4. **Faltou campo** — a ficha fica, `C3` explica em português, nenhuma viagem é queimada. Teste na
   Task 8.
5. **Nome não cadastrado no OpenPort** — `C3` = pedido, linha em `pedidos.csv`, ficha fica. Teste
   na Task 8.

---

### Task 1: Caminhos do deploy (`caminhos.py`)

**Files:**
- Create: `src/anuncio_navio/caminhos.py`
- Test: `tests/test_caminhos.py`

**Interfaces:**
- Produces: `home() -> Path`, `ficha_dir(root: Path) -> Path`, `ficha(root: Path) -> Path`,
  `arquivo_dir(root: Path) -> Path`, `data_dir(root: Path) -> Path`, `logs_dir(root: Path) -> Path`,
  `tmp_dir(root: Path) -> Path`, `json_dir(root: Path) -> Path`, `config_env(root: Path) -> Path`.
  Todas as funções com `root` são puras (não criam pasta).

- [ ] **Step 1: Write the failing test**

```python
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from anuncio_navio import caminhos


class TestCaminhos(unittest.TestCase):
    def test_home_usa_anuncio_root(self):
        with patch.dict(os.environ, {"ANUNCIO_ROOT": r"C:\tmp\anuncios"}):
            self.assertEqual(caminhos.home(), Path(r"C:\tmp\anuncios"))

    def test_layout_do_deploy(self):
        root = Path(r"C:\tmp\anuncios")
        self.assertEqual(caminhos.ficha(root), root / "ficha" / "ficha_anuncio_navio.xlsx")
        self.assertEqual(caminhos.arquivo_dir(root), root / "ficha" / "arquivo")
        self.assertEqual(caminhos.data_dir(root), root / "data")
        self.assertEqual(caminhos.logs_dir(root), root / "logs")
        self.assertEqual(caminhos.tmp_dir(root), root / "tmp")
        self.assertEqual(caminhos.json_dir(root), root / "data" / "json")
        self.assertEqual(caminhos.config_env(root), root / "config" / ".env")

    def test_home_sem_variavel_e_a_raiz_do_repo(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANUNCIO_ROOT", None)
            self.assertTrue((caminhos.home() / "run.py").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_caminhos -v`
Expected: FAIL `ModuleNotFoundError: No module named 'anuncio_navio.caminhos'` (ou AttributeError)

- [ ] **Step 3: Implement `src/anuncio_navio/caminhos.py`**

`home()` lê `ANUNCIO_ROOT` (como `config.from_env` já faz); sem a variável, `Path(__file__).resolve().parents[2]` (raiz do repo). Pasta `ficha/` com nome fixo `ficha_anuncio_navio.xlsx`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_caminhos -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/caminhos.py tests/test_caminhos.py
git commit -m "feat: caminhos do deploy (ficha, data, logs, tmp)"
```

---

### Task 2: Modelo da ficha em `recursos/`

**Files:**
- Create: `src/anuncio_navio/recursos/ficha_modelo.xlsx` (gerado)
- Create: `ferramentas/gerar_modelo_ficha.py`
- Test: `tests/test_modelo_ficha.py`

**Interfaces:**
- Produces: `gerar(origem: Path, destino: Path) -> Path` em `ferramentas/gerar_modelo_ficha.py`;
  o modelo em `src/anuncio_navio/recursos/ficha_modelo.xlsx` com abas
  `Anúncio`, `COMO PREENCHER`, `HISTÓRICO`, `C3:E3` mesclada, e `A29` dizendo "Salve".

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

import openpyxl

from anuncio_navio import planilha

MODELO = Path(__file__).resolve().parents[1] / "src" / "anuncio_navio" / "recursos" / "ficha_modelo.xlsx"


class TestModeloFicha(unittest.TestCase):
    def test_abas_e_status_mesclado(self):
        wb = openpyxl.load_workbook(MODELO)
        self.assertEqual(wb.sheetnames, ["Anúncio", "COMO PREENCHER", "HISTÓRICO"])
        self.assertIn("C3:E3", [str(r) for r in wb["Anúncio"].merged_cells.ranges])

    def test_instrucao_de_salvar(self):
        ws = openpyxl.load_workbook(MODELO)["Anúncio"]
        self.assertIn("Salve", ws["A29"].value)

    def test_leitor_reconhece_os_rotulos(self):
        campos = planilha.ler_planilha(MODELO)
        for chave in ("nome_navio", "imo", "eta_data", "carga", "agencia", "armador"):
            self.assertIn(chave, campos)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_modelo_ficha -v`
Expected: FAIL `FileNotFoundError` em `ficha_modelo.xlsx`

- [ ] **Step 3: Implement the generator and generate the model**

`ferramentas/gerar_modelo_ficha.py`: abre `ficha_anuncio_navio.xlsx`, mescla `C3:E3` (mantendo o
valor/fórmula em `C3`), cria a aba `HISTÓRICO` com o cabeçalho
`data,navio,imo,viagem,duv,resultado,detalhe` (linha 1 em negrito), troca `A29` por
`✔  Preencheu? Salve (Cmd+S) e FECHE — a ficha nova aparece sozinha.` e acrescenta na aba
`COMO PREENCHER` a linha `A10`: `Ao terminar: salve (Cmd+S) e feche. O robô devolve o resultado na
linha STATUS e prepara a próxima ficha.` Roda:

```bash
python ferramentas/gerar_modelo_ficha.py
```

(script sem argumentos, caminhos fixos: `ficha_anuncio_navio.xlsx` → `src/anuncio_navio/recursos/ficha_modelo.xlsx`)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_modelo_ficha -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add ferramentas/gerar_modelo_ficha.py src/anuncio_navio/recursos/ficha_modelo.xlsx tests/test_modelo_ficha.py
git commit -m "feat: modelo da ficha com status mesclado e aba HISTORICO"
```

---

### Task 3: `planilha` tolera datas e números do Excel

**Files:**
- Modify: `src/anuncio_navio/planilha.py` (`_texto`, `_ler_aba` ramo `DUPLOS`)
- Test: `tests/test_planilha.py` (classe nova no fim)

**Interfaces:**
- Produces: `ler_planilha` aceita célula `datetime`/`date` → `DD/MM/AAAA`, célula `time` →
  `HH:MM`, `float` inteiro → `"1000"`, `float` fracionário → `"8,3"` (vírgula, como a ficha pede).

- [ ] **Step 1: Write the failing test**

```python
class TestCelulasExcel(unittest.TestCase):
    MODELO = Path(__file__).resolve().parents[1] / "src" / "anuncio_navio" / "recursos" / "ficha_modelo.xlsx"

    def test_data_hora_e_numeros(self):
        from datetime import datetime
        from tempfile import TemporaryDirectory
        from pathlib import Path

        import openpyxl

        with TemporaryDirectory() as t:
            p = Path(t) / "ficha.xlsx"
            wb = openpyxl.load_workbook(self.MODELO)
            ws = wb["Anúncio"]
            ws["C6"], ws["C7"] = "VOYAGER", "9553256"
            ws["C12"] = datetime(2026, 11, 28, 7, 30)   # ETA: data+hora na mesma celula
            ws["C19"] = "MIUDEZAS COMESTIVEIS"
            ws["C20"] = 1000.0                          # QTD numerica
            ws["C22"], ws["D22"] = 8.3, 8.3             # calado decimal
            wb.save(p)
            campos = planilha.ler_planilha(p)

        self.assertEqual(campos["eta_data"], "28/11/2026")
        self.assertEqual(campos["eta_hora"], "07:30")
        self.assertEqual(campos["qtd"], "1000")
        self.assertEqual(campos["calado_cheg_proa"], "8,3")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_planilha.TestCelulasExcel -v`
Expected: FAIL com `eta_data == "2026-11-28 07:30:00"` (ou similar)

- [ ] **Step 3: Implement**

Em `_texto`: `datetime`→`"%d/%m/%Y"`; `date`→idem; `time`→`"%H:%M"`; `float` inteiro→`str(int(v))`;
`float` fracionário→`f"{v:g}".replace(".", ",")`. No ramo `DUPLOS`, se `v1` for `datetime` e `v2`
vazio, usar a hora de `v1` em `k2` (e a data em `k1`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_planilha -v`
Expected: PASS (toda a classe, incluindo as antigas)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/planilha.py tests/test_planilha.py
git commit -m "fix: ficha aceita data, hora e numero nativos do Excel"
```

---

### Task 4: Notificação do macOS (`notificar.py`)

**Files:**
- Create: `src/anuncio_navio/notificar.py`
- Test: `tests/test_notificar.py`

**Interfaces:**
- Produces: `notificar(titulo: str, texto: str, *, runner=subprocess.run, sistema: str | None = None) -> bool`
  — `darwin` usa `osascript -e 'display notification "<texto>" with title "<titulo>"'`; demais
  plataformas só logam e devolvem `False`.

- [ ] **Step 1: Write the failing test**

```python
class TestNotificar(unittest.TestCase):
    def test_darwin_chama_osascript(self):
        chamadas = []
        ok = notificar("Anúncio de Navio", "Anúncio 9553256 gravado",
                       runner=lambda cmd, **kw: chamadas.append(cmd), sistema="darwin")
        self.assertTrue(ok)
        self.assertEqual(chamadas[0][:2], ["osascript", "-e"])
        self.assertIn("display notification", chamadas[0][2])
        self.assertIn("Anúncio 9553256 gravado", chamadas[0][2])
        self.assertIn("Anúncio de Navio", chamadas[0][2])

    def test_fora_do_mac_nao_chama_nada(self):
        chamadas = []
        ok = notificar("t", "x", runner=lambda cmd, **kw: chamadas.append(cmd), sistema="win32")
        self.assertFalse(ok)
        self.assertEqual(chamadas, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_notificar -v`
Expected: FAIL `ModuleNotFoundError: anuncio_navio.notificar`

- [ ] **Step 3: Implement**

Aspas e barras escapadas com `json.dumps(texto, ensure_ascii=False)` dentro do script AppleScript.
`runner(cmd, check=False, capture_output=True)` em `try/except` (falha de notificação nunca derruba
o ciclo; loga warning).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_notificar -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/notificar.py tests/test_notificar.py
git commit -m "feat: notificacao nativa do macOS"
```

---

### Task 5: Histórico e pedidos (`historico.py`)

**Files:**
- Create: `src/anuncio_navio/historico.py`
- Test: `tests/test_historico.py`

**Interfaces:**
- Produces: `CABECALHO`, `registrar(root, *, navio, imo, viagem, duv="", resultado="", detalhe="", quando=None) -> None`,
  `linhas(root) -> list[tuple[str, ...]]`, `pedido(root, *, tipo, texto, quando=None) -> None`.
  Arquivos: `data/historico.csv` e `data/pedidos.csv` (cabeçalho `data,tipo,texto`).

- [ ] **Step 1: Write the failing test**

```python
class TestHistorico(unittest.TestCase):
    def test_registrar_e_ler(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            historico.registrar(root, navio="VOYAGER", imo="9553256", viagem="000010",
                                duv="000010", resultado="OK", detalhe="Anúncio confirmado")
            historico.registrar(root, navio="VOYAGER", imo="9553256", viagem="000011",
                                resultado="FALHOU", detalhe="2 armadores com AMELIA")
            linhas = historico.linhas(root)
        self.assertEqual(linhas[0], historico.CABECALHO)
        self.assertEqual(len(linhas), 3)
        self.assertEqual(linhas[1][5], "OK")
        self.assertEqual(linhas[2][3:6], ("000011", "", "FALHOU"))

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_historico -v`
Expected: FAIL `ModuleNotFoundError: anuncio_navio.historico`

- [ ] **Step 3: Implement**

CSV UTF-8 com `newline=""`, cabeçalho escrito uma vez. `quando` aceita `datetime` (default `now()`),
formato `%d/%m/%Y %H:%M`. `pedido` grava `data,tipo,texto`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_historico -v`
Expected: PASS (2 testes: registrar/ler e pedido)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/historico.py tests/test_historico.py
git commit -m "feat: historico.csv e pedidos.csv do servico"
```

---

### Task 6: Ciclo de vida da ficha (`ficha.py` — estado, resultado, arquivo, nova)

**Files:**
- Create: `src/anuncio_navio/ficha.py`
- Test: `tests/test_ficha.py`

**Interfaces:**
- Produces:
  - `esta_livre(path: Path, *, agora: float | None = None, estavel_seg: float = 5.0, lsof=None) -> bool`
  - `escrever_status(path: Path, mensagem: str) -> None` (grava na `C3`, vermelho, e salva atômico)
  - `arquivar(root: Path, origem: Path, *, imo: str, viagem: str, duv: str, quando=None) -> Path`
    (destino `ficha/arquivo/<imo>_<viagem>__<AAAAMMDD_HHMMSS>__DUV<duv>.xlsx`)
  - `gerar_nova(root: Path) -> Path` (copia o modelo, preenche a aba `HISTÓRICO` com `historico.linhas` e faz `os.replace` na ficha)
  - `marcar_estado(root: Path, path: Path) -> None` e `ja_tentada(root: Path, path: Path) -> bool`
    (`data/estado_ficha.json` com `{"mtime": float, "tamanho": int}`)

- [ ] **Step 1: Write the failing test**

```python
class TestEstaSempre(unittest.TestCase):
    def test_ficha_recem_salva_nao_esta_livre(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "f.xlsx"
            p.write_bytes(b"x")
            agora = p.stat().st_mtime + 1
            self.assertFalse(ficha.esta_livre(p, agora=agora))
            self.assertTrue(ficha.esta_livre(p, agora=agora + 60, lsof=lambda _p: ""))
            (Path(t) / ".~lock.f.xlsx#").write_text("lock")
            self.assertFalse(ficha.esta_livre(p, agora=agora + 60, lsof=lambda _p: ""))

    def test_lsof_aberto_bloqueia(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "f.xlsx"
            p.write_bytes(b"x")
            self.assertFalse(ficha.esta_livre(p, agora=p.stat().st_mtime + 60, lsof=lambda _p: "123"))


class TestCicloDaFicha(unittest.TestCase):
    def test_escrever_status_preserva_o_resto(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "f.xlsx"
            shutil.copyfile(MODELO, p)
            ficha.escrever_status(p, "NÃO FOI ENVIADO — teste")
            ws = openpyxl.load_workbook(p)["Anúncio"]
            self.assertEqual(ws["C3"].value, "NÃO FOI ENVIADO — teste")
            self.assertEqual(ws["A3"].value, "STATUS")

    def test_arquivar_move_com_duv(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            (root / "ficha").mkdir()
            p = root / "ficha" / "ficha_anuncio_navio.xlsx"
            shutil.copyfile(MODELO, p)
            destino = ficha.arquivar(root, p, imo="9553256", viagem="000010", duv="000010")
            self.assertFalse(p.exists())
            self.assertEqual(destino.parent, root / "ficha" / "arquivo")
            self.assertIn("9553256_000010", destino.name)
            self.assertIn("DUV000010", destino.name)

    def test_gerar_nova_traz_historico(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            (root / "ficha").mkdir()
            historico.registrar(root, navio="VOYAGER", imo="9553256", viagem="000009",
                                duv="000009", resultado="OK", detalhe="confirmado")
            nova = ficha.gerar_nova(root)
            ws = openpyxl.load_workbook(nova)["HISTÓRICO"]
            self.assertEqual([c.value for c in ws[1]], list(historico.CABECALHO))
            self.assertIn("000009", [c.value for c in ws[2]])

    def test_estado_evita_reprocessar(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            (root / "ficha").mkdir()
            p = root / "ficha" / "ficha_anuncio_navio.xlsx"
            shutil.copyfile(MODELO, p)
            ficha.marcar_estado(root, p)
            self.assertTrue(ficha.ja_tentada(root, p))
            os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 10))
            self.assertFalse(ficha.ja_tentada(root, p))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ficha -v`
Expected: FAIL `ModuleNotFoundError: anuncio_navio.ficha`

- [ ] **Step 3: Implement**

- `esta_livre`: `os.stat`; `mtime` mais novo que `agora - estavel_seg` → `False`; `glob(".~lock.*#")`
  na pasta → `False`; `lsof(path)` (default: `lsof -t <path>` via subprocess, vazio se indisponível)
  com saída não vazia → `False`.
- `escrever_status`: `load_workbook(p)` (não read_only), `ws["C3"] = mensagem`, `Font(bold=True,
  color="9C0006")`, `PatternFill("solid", fgColor="FFC7CE")`, `Alignment(wrap_text=True)`, salva em
  `tmp` da mesma pasta e `os.replace`.
- `arquivar`: `os.makedirs(arquivo_dir)`, `shutil.move`.
- `gerar_nova`: copia `MODELO` (Path do módulo → `recursos/ficha_modelo.xlsx`) para tmp, regrava a
  aba `HISTÓRICO` (apaga `A2:G∞` e reescreve `historico.linhas(root)`), `os.replace` em
  `caminhos.ficha(root)`; garante a pasta `ficha/`.
- `marcar_estado`: JSON atômico (`tempfile.mkstemp` + `os.replace`, padrão do `sequencia.py`);
  `ja_tentada`: compara `mtime` e `tamanho` (tolerância 0).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ficha -v`
Expected: PASS (6 testes)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/ficha.py tests/test_ficha.py
git commit -m "feat: ciclo de vida da ficha (resultado, arquivo, nova, estado)"
```

---

### Task 7: Leitura amigável da ficha (`ficha.ler`)

**Files:**
- Modify: `src/anuncio_navio/ficha.py`
- Test: `tests/test_ficha_leitura.py`

**Interfaces:**
- Produces: `ROTULOS_PT: dict[str, str]`, `ler(root: Path) -> tuple[dict, list[str]]`,
  `mensagem_invalida(pendencias: list[str]) -> str`. A leitura é sempre por cópia em `tmp/` (a
  ficha original não é aberta; compatível com Excel aberto).

- [ ] **Step 1: Write the failing test**

```python
class TestLeitura(unittest.TestCase):
    def _ficha_com(self, root, valores):
        p = root / "ficha" / "ficha_anuncio_navio.xlsx"
        shutil.copyfile(MODELO, p)
        wb = openpyxl.load_workbook(p)
        for cel, v in valores.items():
            wb["Anúncio"][cel] = v
        wb.save(p)
        return p

    def test_faltando_campos_vira_mensagem(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            (root / "ficha").mkdir()
            self._ficha_com(root, {"C6": "VOYAGER"})
            campos, pendencias = ficha.ler(root)
            msg = ficha.mensagem_invalida(pendencias)
        self.assertEqual(campos["nome_navio"], "VOYAGER")
        self.assertEqual(campos["imo"], "")
        self.assertIn("IMO", pendencias)
        self.assertTrue(msg.startswith("NÃO FOI ENVIADO —"))
        self.assertIn("Corrija e salve de novo.", msg)

    def test_ficha_valida_nao_tem_pendencias(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            (root / "ficha").mkdir()
            self._ficha_com(root, self.CAMPOS_OK)
            campos, pendencias = ficha.ler(root)
        self.assertEqual(pendencias, [])
        self.assertEqual(campos["porto_prox"], "Santos")

    CAMPOS_OK = {
        "C6": "VOYAGER", "C7": "9553256", "C8": "190", "C11": "Ilheus",
        "C12": "28/11/2026", "D12": "07:30", "C13": "29/11/2026", "D13": "08:00",
        "C14": "30/11/2026", "D14": "12:00", "C15": "30/11/2026", "D15": "19:00",
        "C16": "Santos", "C17": "BERÇO 101", "C19": "MIUDEZAS COMESTIVEIS",
        "C20": "1000", "C21": "1000", "C22": "8,30", "D22": "8,30",
        "C23": "8,30", "D23": "8,30", "C25": "MARINAV", "C26": "AMELIA",
        "C27": "INTERMARIT", "C28": "AEC SHIPPING",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ficha_leitura -v`
Expected: FAIL `AttributeError: module 'anuncio_navio.ficha' has no attribute 'ler'`

- [ ] **Step 3: Implement**

`ler`: copia `caminhos.ficha(root)` para `tmp/ficha_<ts>.xlsx`, `planilha.ler_planilha(copia)` e
`planilha.validar_campos`, remove a cópia no `finally`. Traduzir erros:
`Campo obrigatorio vazio: <k>.` → `ROTULOS_PT[k]`; `IMO deve ter ...` → `IMO deve ter 7 números`;
demais mensagens passam como estão. `mensagem_invalida`: se todas as pendências forem nomes de
campo (sem "deve"), `NÃO FOI ENVIADO — faltam {n} campo(s): {", ".join(...)}. Corrija e salve de
novo.`; senão `NÃO FOI ENVIADO — {"; ".join(pendencias)}. Corrija e salve de novo.`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ficha_leitura -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/ficha.py tests/test_ficha_leitura.py
git commit -m "feat: leitura da ficha com pendencias em portugues"
```

---

### Task 8: Um ciclo do serviço (`servico.py`)

**Files:**
- Create: `src/anuncio_navio/servico.py`
- Modify: `src/anuncio_navio/status.py` (`mesmo_anuncio`)
- Test: `tests/test_servico.py`

**Interfaces:**
- Produces: `Resultado(estado: str, mensagem: str = "", duv: str = "")` e
  `processar(root: Path, cfg, *, executar=None, agora=None, notificar_fn=None) -> Resultado`,
  com `estado` em `sem_ficha | ocupada | sem_novidade | invalida | falhou | ok | duplicado`.
  `status.mesmo_anuncio(cfg, d) -> str` devolve o DUV já registrado para o mesmo `imo` + mesma
  `eta` (`"DD/MM/AAAA HH:MM"`), ou `""`. Para isso `status.marcar_ok` passa a gravar também
  `"eta": d.get("eta")` (entradas antigas sem `eta` simplesmente não casam).

- [ ] **Step 1: Write the failing test**

```python
class TestProcessar(unittest.TestCase):
    CAMPOS = {
        "C6": "VOYAGER", "C7": "9553256", "C8": "190", "C11": "Ilheus",
        "C12": "28/11/2026", "D12": "07:30", "C13": "29/11/2026", "D13": "08:00",
        "C14": "30/11/2026", "D14": "12:00", "C15": "30/11/2026", "D15": "19:00",
        "C16": "Santos", "C17": "BERÇO 101", "C19": "MIUDEZAS COMESTIVEIS",
        "C20": "1000", "C21": "1000", "C22": "8,30", "D22": "8,30",
        "C23": "8,30", "D23": "8,30", "C25": "MARINAV", "C26": "AMELIA",
        "C27": "INTERMARIT", "C28": "AEC SHIPPING",
    }

    def _ficha(self, root, campos=None):
        p = root / "ficha" / "ficha_anuncio_navio.xlsx"
        shutil.copyfile(MODELO, p)
        wb = openpyxl.load_workbook(p)
        for cel, v in (campos or self.CAMPOS).items():
            wb["Anúncio"][cel] = v
        wb.save(p)
        return p

    def _root_preenchido(self, t):
        root = Path(t)
        (root / "ficha").mkdir()
        self._ficha(root)
        return root

    def _cfg(self, root):
        return config.Config(
            url=config.URL_QAS, login="login", senha="senha", headless=True,
            primeiro_plano=True, timeout_ms=30000, slow_mo_ms=0, pausa_visual_ms=0,
            manter_aberto_seg=0, project_root=root, ambiente="QAS")

    def test_sucesso_arquiva_e_gera_nova(self):
        with TemporaryDirectory() as t:
            root = self._root_preenchido(t)
            cfg = self._cfg(root)
            avisos = []
            def anunciar(c, d):
                status.marcar_ok(c, d, "000010")   # executar_um real faz isso
                return "000010"
            r = servico.processar(root, cfg, executar=anunciar,
                                  notificar_fn=lambda ti, tx: avisos.append((ti, tx)))
            self.assertEqual(r.estado, "ok")
            self.assertEqual(r.duv, "000010")
            self.assertEqual(list((root / "ficha" / "arquivo").glob("*.xlsx"))[0].name.count("DUV000010"), 1)
            self.assertTrue((root / "ficha" / "ficha_anuncio_navio.xlsx").exists())
            self.assertEqual(historico.linhas(root)[-1][5], "OK")
            self.assertIn("DUV 000010", avisos[0][1])

    def test_invalida_mantem_a_ficha_e_nao_reserva_viagem(self):
        with TemporaryDirectory() as t:
            root = Path(t); (root / "ficha").mkdir()
            shutil.copyfile(MODELO, root / "ficha" / "ficha_anuncio_navio.xlsx")
            r = servico.processar(root, self._cfg(root), executar=lambda c, d: "x",
                                  notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "invalida")
            self.assertFalse((root / "ficha" / "arquivo").exists())
            self.assertFalse((root / "data" / "sequencia.json").exists())
            c3 = openpyxl.load_workbook(root / "ficha" / "ficha_anuncio_navio.xlsx")["Anúncio"]["C3"].value
            self.assertTrue(c3.startswith("NÃO FOI ENVIADO — faltam"))

    def test_pedido_grava_pedidos_e_mantem(self):
        with TemporaryDirectory() as t:
            root = self._root_preenchido(t)
            def falhar(c, d):
                raise exceptions.LookupError("PEDIDO: armador 'AMELIA' nao cadastrado.")
            r = servico.processar(root, self._cfg(root), executar=falhar,
                                  notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "falhou")
            self.assertIn("PEDIDO", (root / "data" / "pedidos.csv").read_text(encoding="utf-8"))
            self.assertTrue((root / "ficha" / "ficha_anuncio_navio.xlsx").exists())

    def test_duplicado_por_conteudo_nao_chama_o_robo(self):
        with TemporaryDirectory() as t:
            root = self._root_preenchido(t)
            cfg = self._cfg(root)
            chamou = []
            def anunciar(c, d):
                status.marcar_ok(c, d, "000010")
                return "000010"
            servico.processar(root, cfg, executar=anunciar,
                              notificar_fn=lambda ti, tx: None)
            # simula a ficha antiga (ja arquivada) re-salva por cima da nova
            arquivada = next((root / "ficha" / "arquivo").glob("*.xlsx"))
            p = root / "ficha" / "ficha_anuncio_navio.xlsx"
            shutil.copyfile(arquivada, p)
            velho = p.stat().st_mtime - 60
            os.utime(p, (velho, velho))
            r = servico.processar(root, self._cfg(root),
                                  executar=lambda c, d: chamou.append(1) or "000011",
                                  notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "duplicado")
            self.assertEqual(r.duv, "000010")
            self.assertEqual(chamou, [])

    def test_ficha_parada_nao_roda_de_novo(self):
        with TemporaryDirectory() as t:
            root = Path(t); (root / "ficha").mkdir()
            shutil.copyfile(MODELO, root / "ficha" / "ficha_anuncio_navio.xlsx")
            cfg = self._cfg(root)
            servico.processar(root, cfg, executar=lambda c, d: "x", notificar_fn=lambda ti, tx: None)
            r = servico.processar(root, cfg, executar=lambda c, d: "x", notificar_fn=lambda ti, tx: None)
            self.assertEqual(r.estado, "sem_novidade")
```

`_cfg(root)` devolve `Config` mínimo (`project_root=root`, `ambiente="QAS"`) montado com
`dataclasses.replace` ou `Config(...)` direto.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_servico -v`
Expected: FAIL `ModuleNotFoundError: anuncio_navio.servico`

- [ ] **Step 3: Implement**

Ordem exata do ciclo:

1. `p = caminhos.ficha(root)`; se não existe → `ficha.gerar_nova(root)` e `Resultado("sem_ficha")`.
2. `ficha.ja_tentada(root, p)` → `Resultado("sem_novidade")` (**antes** de `esta_livre`: a ficha que
   o robô acabou de escrever tem `mtime` novo e não pode virar "ocupada").
3. `not ficha.esta_livre(p)` → `Resultado("ocupada")` (sem notificar; o loop notifica uma vez).
4. `campos, pendencias = ficha.ler(root)`; se pendencias → `ficha.escrever_status(mensagem)`,
   histórico `FALHOU`, `ficha.marcar_estado` (depois da escrita), notifica falha,
   `Resultado(estado="invalida", mensagem=msg)`.
5. `payload = planilha.construir_payload(campos)`; `dup = status.mesmo_anuncio(cfg, payload)`;
   se `dup` → arquiva (`duv=dup`), histórico `JÁ ANUNCIADO`, `gerar_nova`, `marcar_estado` na ficha
   nova, notifica duplicado, `Resultado(estado="duplicado", duv=dup)`.
6. `payload["viagem"] = sequencia.proxima(root)`; `arquivo = caminhos.json_dir(root)/f"{imo}_{viagem}.json"` gravado com `json.dumps(payload, ensure_ascii=False, indent=2)`;
   `dados = fila_json.carregar_anuncio(arquivo)`.
7. `executar = executar or main.executar_um`; `duv = executar(cfg, dados)` dentro de `try`:
   - `LoginError` → mensagem senha; `LookupError` → mensagem `NÃO FOI ENVIADO — {e}` + `pedido(...)`;
   - `Exception` → mensagem genérica com a primeira linha.
   Em qualquer exceção: `fila_json.finalizar_erro(arquivo, erro)`, `escrever_status`, histórico
   `FALHOU`, `marcar_estado`, notifica falha, `Resultado(estado="falhou", mensagem=msg)`.
8. `duv == "duplicado"` → arquiva, histórico `JÁ ANUNCIADO`, nova, notifica,
   `Resultado(estado="duplicado", mensagem=..., duv="")`.
9. senão → `fila_json.finalizar_sucesso(arquivo, duv)`, histórico `OK` (**antes** de gerar a nova,
   para ela já sair com a linha), arquiva (com `duv`), `gerar_nova`, `marcar_estado` na ficha nova,
   notifica ok, `Resultado(estado="ok", duv=duv)`.

`status.marcar_ok` é chamado por `main.executar_um`; ao acrescentar `"eta"` lá, o `status.json`
passa a permitir a checagem por conteúdo (item 5).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_servico -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/servico.py src/anuncio_navio/status.py tests/test_servico.py
git commit -m "feat: ciclo do servico (valida, anuncia, arquiva, gera nova ficha)"
```

---

### Task 9: `monitor_fila.py --servico` (trava + loop)

**Files:**
- Create: `src/anuncio_navio/trava.py`
- Modify: `monitor_fila.py`
- Test: `tests/test_trava.py`, `tests/test_monitor_servico.py`

**Interfaces:**
- Produces: `trava.adquirir(path: Path, *, agora=None, validade_min: int = 120) -> bool`,
  `trava.liberar(path: Path) -> None`; `monitor_fila.modo_servico(intervalo: float, uma_vez: bool,
  *, processar_fn=None, dormir=time.sleep) -> int`.

- [ ] **Step 1: Write the failing test**

```python
class TestTrava(unittest.TestCase):
    def test_segunda_instancia_nao_entra(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "servico.lock"
            self.assertTrue(trava.adquirir(p))
            self.assertFalse(trava.adquirir(p))
            trava.liberar(p)
            self.assertTrue(trava.adquirir(p))

    def test_lock_velho_e_roubado(self):
        with TemporaryDirectory() as t:
            p = Path(t) / "servico.lock"
            p.write_text("123 2000-01-01T00:00:00")
            self.assertTrue(trava.adquirir(p, agora=time.time()))
```

`modo_servico` com `processar_fn` fake: uma passada (`uma_vez=True`) chama `processar_fn` uma vez e
devolve 0; se `adquirir` falhar, não chama e devolve 0.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_trava tests.test_monitor_servico -v`
Expected: FAIL `ModuleNotFoundError: anuncio_navio.trava`

- [ ] **Step 3: Implement**

`trava`: arquivo com `<pid> <isoformat(timespec="seconds")>`; se existir e a idade for menor que
`validade_min`, `False`; mais velho (ou ilegível) → sobrescreve com `os.replace` de um temporário. `liberar` remove. `monitor_fila.py`: flag
`--servico`; quando presente, `logging` com `FileHandler(caminhos.logs_dir(root)/"servico.log")`,
`trava.adquirir`, loop chamando `servico.processar(caminhos.home(), cfg)`; em `ocupada`, notifica
uma vez por episódio (guarda o `mtime` notificado); `KeyboardInterrupt` → libera e sai.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_trava tests.test_monitor_servico -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add src/anuncio_navio/trava.py monitor_fila.py tests/test_trava.py tests/test_monitor_servico.py
git commit -m "feat: modo --servico com trava de instancia unica"
```

---

### Task 10: Documentação e verificação no QAS

**Files:**
- Modify: `README.md` (seção nova "Serviço da ficha única"), `memory.md`
- Test: nenhum (verificação manual)

- [ ] **Step 1: Documentar**

README: layout do deploy (`ficha/`, `data/`, `logs/`, `tmp/`), como rodar em desenvolvimento
(`python monitor_fila.py --servico --uma-vez` com `ANUNCIO_ROOT` apontando para uma pasta de
teste), as regras (arquiva/gera nova, ficha parada não roda, duplicado por IMO+ETA) e que o
instalador macOS é o Plano B.

- [ ] **Step 2: Verificação manual no QAS (sem gravar)**

```powershell
$t = "$env:TEMP\anuncio_smoke"; New-Item -ItemType Directory -Force $t\ficha | Out-Null
Copy-Item src\anuncio_navio\recursos\ficha_modelo.xlsx $t\ficha\ficha_anuncio_navio.xlsx
$env:ANUNCIO_ROOT = $t
python monitor_fila.py --servico --uma-vez    # esperado: cria a ficha em branco / "invalida"
```

Preencher a ficha com um caso QAS válido e rodar de novo **sem** `CONFIRMAR_ANUNCIO` (para o robô
gravar em QAS e parar antes de confirmar; a ficha deve ser arquivada, a nova criada e o
`data/historico.csv` receber a linha). Conferir `data/json/` e `ficha/arquivo/`.

- [ ] **Step 3: Commit**

```bash
git add README.md memory.md
git commit -m "docs: servico da ficha unica (modo --servico)"
```

---

## Self-Review

- Cobertura da spec: layout/caminhos (T1), modelo e status mesclado (T2), Excel nativo (T3),
  notificação (T4), histórico/pedidos (T5), ciclo de arquivo/nova/estado (T6), leitura amigável (T7),
  orquestração/duplicidade (T8), serviço/trava (T9), docs e prova QAS (T10). Instalador macOS,
  Keychain, plist e pacote = Plano B.
- Consistência de tipos: `Resultado.estado` idêntico em T8/T9; `caminhos` usado por T6/T8/T9;
  `historico.registrar` consumido por T8 e T6 (`gerar_nova` lê `linhas`).
- Decisão de escopo: Plano B (instalador) só depois deste, porque consome `caminhos`, `notificar`,
  `trava` e `--servico`.
