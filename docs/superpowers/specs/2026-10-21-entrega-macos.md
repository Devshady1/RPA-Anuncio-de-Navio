# Especificação — RPA de Anúncio de Navio: entrega sem erros no Mac do agente

**Data:** 2026-10-21 · **Status:** proposta para revisão · **Autor:** estagiário CODEBA (autor do RPA)

---

## 1. Objetivo

Entregar o RPA de anúncio de navio a um operador de agência marítima, de idade avançada e
pouco familiarizado com sistemas, de forma **à prova de erro**: ele preenche uma planilha,
salva, e o sistema faz o resto — sem terminal, sem copiar arquivos, sem renomear, sem
"travou", sem esperar 60 segundos olhando um navegador.

Sucesso = o operador nunca precisa aprender nada além de "preencher a planilha e salvar".

## 2. Contexto (estado atual verificado no código)

| Fato | Onde |
|---|---|
| A ficha `ficha_anuncio_navio.xlsx` mora na **raiz** do projeto; o RPA só lê `.xlsx` dentro de `entrada/` | `inserir.py`, `monitor_fila.py` |
| O operador precisa **copiar** a ficha para `entrada/` (a planilha diz "Devolva este arquivo" sem dizer para onde) | `ficha_anuncio_navio.xlsx` A29 |
| O monitor é um **processo de terminal** com `glob` a cada 10 s; não há tarefa agendada | `monitor_fila.py:36-39,71` |
| Se o Excel estiver aberto, o `shutil.move` falha com `PermissionError` → "travado" → só resolve no ciclo seguinte | `inserir.py:83-89` |
| O navegador abre **visível e maximizado**, e `browser.bloquear(page)` **trava o mouse** | `config.py:59-60`, `main.py:19-22,48-60` |
| Nada volta para a planilha: sucesso só aparece no console + `dados_rpa/processados/`; erro vira `entrada/erro/*.log.txt` com texto de programador (`ValueError: Ficha rejeitada: - Campo obrigatorio vazio: imo.`) | `inserir.py:117` |
| A planilha **já tem** célula de status com fórmula (`C3 = OK — PRONTO PARA ENVIAR` / `FALTAM N CAMPO(S)`) e uma aba `COMO PREENCHER` — ou seja, a interface boa já está desenhada, só não está ligada ao RPA | `ficha_anuncio_navio.xlsx` |

O RPA em si funciona: **24 rodadas, 0 falhas, 1 anúncio gravado em PROD** (TI SUNRISE, DUV
`9701009_000006`, 13/10/2026), 35 testes passando. O problema **não é o robô** — é a entrega.

## 3. Decisões de produto (a interface do operador)

1. **Uma pasta, um arquivo, uma ação.** A planilha nasce dentro da pasta monitorada, com nome
   fixo. O operador abre, preenche, `Ctrl+S`, **fecha**. Não copia, não move, não renomeia.
2. **O RPA devolve o resultado na própria planilha.** Célula `C3` passa de fórmula para
   resultado escrito pelo robô (`OK — PRONTO PARA ENVIAR`, `FALHOU: ...`), mais uma aba
   `HISTÓRICO` com uma linha por tentativa (viagem, DUV, data, resultado).
3. **Falha nunca apaga o trabalho.** Se faltar campo, o robô escreve a pendência na `C3` e
   na aba `HISTÓRICO` e **deixa a planilha onde está**; o operador corrige e salva de novo.
4. **Um aviso do sistema operacional** ("Anúncio 9701009_000006 gravado") — o operador não
   precisa ficar olhando o console.
5. **A planilha é a única interface.** Sem janelas, sem botões, sem "abrir programa".
6. **O agente nunca liga para ninguém** por causa do anúncio. Se algo estiver errado no
   cadastro (falta navio, falta armador), isso é **pedido de cadastro** — tarefa da CODEBA —
   e vira item numa fila, não uma ligação para o estagiário.

## 4. Decisões de arquitetura

1. **O RPA roda no MacBook do operador**, não em servidor. O OpenPort é corporativo e o
   acesso é por credencial do usuário; o Mac já tem o perfil logado.
2. **Credencial = a conta do próprio operador** (mesmos acessos do usuário humano). Consequência
   prática: se a senha do OpenPort mudar, o robô falha com a mensagem "a senha do OpenPort
   mudou" — e o `ATUALIZAR.command`/`config/.env` é o ponto de correção.
3. **Serviço invisível** (`launchd` LaunchAgent, `RunAtLoad`) — sem terminal aberto, sem janela.
   `HEADLESS=true`, `PRIMEIRO_PLANO=false`, `MANTER_ABERTO_SEG=0`.
4. **Pastas de trabalho fora de Documentos/Área de Trabalho/iCloud Drive** (o macOS bloqueia
   escrita e renomeio em pastas sincronizadas). Layout:
   `~/CODEBA/AnuncioNavio/{app,config,dados,ficha,logs}`.
5. **Atualização por troca de pasta**, não por instalador: `ATUALIZAR.command` substitui
   **apenas** `app/` (e `tabelas/`), nunca `config/` nem `dados/`.
6. **Estado fora do Mac.** `dados/sequencia.json` e `dados/status.json` são o contador de DUV e
   a trava anti-duplicidade; precisam de backup (a pasta de troca ou o e-mail de fase 1).
7. **Contrato estável para as próximas automações.** O RPA é a automação nº 1 da CODEBA; o
   JSON em `dados_rpa/` é o ponto de extensão (QA/torre RPA). Nenhuma mudança de layout pode
   quebrar esse contrato.

## 5. Motor de resolução dos lookups (núcleo — o que o reconhecimento revelou)

### 5.1 O problema que existia

Os 8 campos de classificação do anúncio (agência, portos, armador, afretador, berço,
operador, tipo de mercadoria) são preenchidos hoje com **códigos** que o RPA resolve a partir de
**tabelas CSV locais** (`tabelas/agencias.csv`, `armadores.csv`, `operadores.csv`, `portos.csv`,
`cargas.csv`). Essas tabelas são **cópias** — e a cópia envelhece. Caso real: armador novo
(TAMAR) cadastrado na PROD e ausente do CSV, obrigando o código a ser informado à mão
(`memory.md:313`, `ferramentas/relatorio_prod.py:138`).

### 5.2 O que o reconhecimento no QAS (21/10/2026) provou

Cada campo da tela 2003 tem um botão **"Localizar"** que abre uma **consulta do próprio
OpenPort** (read-only). O conteúdo dessas consultas é **exatamente** a fonte das tabelas CSV —
a versão viva. E o popup sabe preencher os campos sozinho.

| Campo | Visível | Hidden | Botão lupa | Popup (WCI) | Filtro descrição | Filtro código | Colunas da grade |
|---|---|---|---|---|---|---|---|
| Agência | `NUM_AGENCIA_2` | `NUM_AGENCIA` | `ANUM_AGENCIA` | `dlgPsqAgenteUsuario` | `sqlNOM_FANTASIA` | `SqlCOD_EMPRESA` | Código, Descrição |
| Porto origem | `NUM_PORTO_ANT_2` | `NUM_PORTO_ANT` | `ANUM_PORTO_ANT` | `dlgPsqPortoOrigem` | `sqlFiltroDescricao` | `sqlCOD_PORTO` | Código, Descrição |
| Porto próximo | `NUM_PORTO_PROX_2` | `NUM_PORTO_PROX` | `ANUM_PORTO_PROX` | `dlgPsqPortoProximo` | `sqlFiltroDescricao` | `sqlCOD_PORTO` | Código, Descrição |
| Armador | `NUM_ARMADOR_2` | `NUM_ARMADOR` | `ANUM_ARMADOR` | `dlgPsqArmador` | `sqlFiltroDescricao` | `sqlCOD_EMPRESA` | Código, Descrição |
| Afretador | `NUM_AFRETADOR_2` | `NUM_AFRETADOR` | `ANUM_AFRETADOR` | `dlgPsqAfretador` | `sqlFiltroDescricao` | `sqlCOD_EMPRESA` | Código, Descrição |
| Berço | `NUM_BERCO_2` | `NUM_BERCO` | `ANUM_BERCO` | `dlgPsqBercoPosAtrac` | `sqlDCR_BERCO` | `sqlCOD_BERCO` | Cod., Berço, Cod., Posição, Cais |
| Operador | `NUM_OPERADOR_2` | `NUM_OPERADOR` | `ANUM_OPERADOR` | `dlgPsqOperPortuario` | `sqlFiltroDescricao` | `sqlCOD_EMPRESA` | Código, Descrição |
| Tipo mercadoria | `NUM_TIP_MERCAD_2` | `NUM_TIP_MERCAD` | `ANUM_TIP_MERCAD` | `dlgPsqTpGrupoMercadPred` | `sqlDCR_TIP_MERCAD` | `sqlCOD_TIP_MERCAD` | Codigo, Desc. Resumida, Cod Grupo, Grupo, Mercadoria |

Verificado em QAS: 30010 = MARINAV (agência) · 60700 = AMELIA NAVIGATION · 30002 = INTERMARIT
(operador) · 101 = BERÇO 101 · 02061000 = MIUDEZAS COMESTIVEIS (NCM) · **BRIOS = Ilhéus**
(UN/LOCODE).

### 5.3 Regras do popup (medidas, não suposições)

- A busca é **prefixo** ("começa com"), **insensível a maiúsculas** e **sensível a acento**
  (`IRMÃOS` encontra `IRMÃOS BRITTO`; `IRMAOS` não encontra; `ILH` encontra `Ilhéus`, `ILHE` não).
- Descrição e código são filtros **independentes que se combinam (AND)**; qualquer um pode ficar vazio.
- A caixa **"sem paginação"** traz o resultado inteiro (ex.: 1.369 portos com prefixo "A").
- A grade mostra, na 1ª célula, um link `<a onclick="window.opener.QueryValor(...)">`;
  **clicar nele é o que seleciona** — o popup se fecha sozinho e o OpenPort preenche
  hidden + visível + descrição.
- `QueryValor` grava: hidden = id interno do registro (`12895`, `12970`, …), visível = **código**
  (`30010`, `60700`), span = **descrição**. É o **mesmo formato** do caminho "digitar código + TAB".
- Na seleção, o popup de berço também preenche `NUM_POSICAO_ATRACACAO*` (código de posição).

### 5.4 Algoritmo de resolução (novo motor)

Para cada um dos 8 campos, com o texto que o operador escreveu na planilha:

1. Se o texto estiver vazio → campo ignorado.
2. Abrir o popup do campo; marcar "sem paginação".
3. **Consultas em sequência**, parando na primeira que devolver linhas:
   a) o texto como o operador escreveu (preservando acentos);
   b) o texto sem a última palavra (`"MARINAV LTDA"` → `"MARINAV"`);
   c) prefixos decrescentes do termo até 4 caracteres (`"MARINAV"` → `MARINA`, `MARIN`, `MARI`).
   Se o texto parecer um código, tentar também o filtro de código com o mesmo texto.
4. **Escolha local** entre as linhas devolvidas, comparando descrição normalizada
   (sem acento, caixa alta, espaços colapsados):
   - igualdade exata → automático;
   - só uma linha devolvida e compatível → automático;
   - prefixo de um lado → automático se for o melhor e único;
   - empate/ambiguidade → **não escolhe**: devolve os candidatos para a fila de pedidos.
5. Clicar no link da linha escolhida → o OpenPort preenche os campos.
6. **Verificar**: se o campo hidden ficou preenchido → resolvido. Caso contrário → fallback
   para o caminho atual (digitar código + TAB) e, se ainda assim falhar, registrar pendência.

### 5.5 Consequências

- **As tabelas CSV deixam de ser a fonte primária** — viram *fallback* offline e auxiliar de
  busca por "contém". O caso TAMAR se resolve sozinho assim que a CODEBA cadastra o armador.
- O operador passa a poder escrever **nomes**, que é o que ele conhece.
- Desaparecem os erros "Armador Afretador não pode ficar vazio" causados por tabela desatualizada.

### 5.6 Defeitos encontrados no código atual (a corrigir)

1. `browser._achar_botao_lupa` procura o botão via `xpath=ancestor::tr[1]` — mas a tela 2003 é
   baseada em `div.input-group.lookup`, **não em `<tr>`**. O localizador genérico **nunca**
   encontra o botão. Só a agência funciona, porque `config.py:75` passa o seletor explícito
   `#ANUM_AGENCIA`.
2. `browser._resolver_via_lupa` seleciona por **radio + botão OK** — o popup **não tem radio nem
   botão OK**; a seleção é o link `<a>` da 1ª célula. (Por isso o fallback "nunca" funcionou.)
3. `browser._resolver_via_lupa` preenche `input[type=text]` **primeiro** do popup, que é o campo
   de **código**; o campo de **descrição** nunca era usado — e o filtro de código não é
   confiável para o popup de portos (códigos UN/LOCODE não batem com o filtro).

## 6. Fluxos de erro

| Situação | O que o robô faz | O que o operador vê |
|---|---|---|
| Falta campo obrigatório | Não grava nada; anota em `HISTÓRICO`; mantém a planilha | `C3` = "FALTAM 2 CAMPOS (IMO, TIPO DE CARGA)" |
| Nome não encontrado no cadastro | Não grava; cria item em `dados/pedidos.csv` | `C3` = "PEDIDO: armador 'X' não cadastrado" + notificação |
| Nome ambíguo | Não grava; cria item em `dados/pedidos.csv` com os candidatos | `C3` = "PEDIDO: 2 armadores com 'AMELIA' — escolha" |
| Erro de senha | Não grava | `C3` = "a senha do OpenPort mudou" |
| OpenPort fora do ar / timeout | Não grava; tenta de novo no ciclo seguinte | `C3` = "OpenPort indisponível, tentando de novo" |
| Já anunciado (mesma viagem + DUV) | Não duplica | `C3` = "JÁ ANUNCIADO (DUV 000006)" |

**Regra anti-duplicidade:** o par (viagem, DUV) fica registrado em `dados/status.json`; se a
mesma planilha for salva de novo com o mesmo conteúdo, o robô reconhece e não regrava.

## 7. Instalação no macOS do operador

1. `ATUALIZAR.command` (duplo clique) instala/atualiza `app/`, `config/` e `dados/`.
2. `launchd` LaunchAgent: `com.codeba.anuncionavio`, `RunAtLoad`, `KeepAlive`, executa
   `python3 monitor_fila.py --servico` com `HEADLESS=true`.
3. **O Mac não pode dormir** com o robô ligado: instrução de energia (prevenir suspensão na
   tomada) — o robô não roda com a tela apagada por suspensão.
4. A pasta de trabalho fica fora de pastas sincronizadas.
5. `.env` (URL, credencial) fica em `config/` e **não** é substituído por atualizações.

## 8. Distribuição e atualização

- **Fase 1 (sem infra nova):** e-mail (SMTP em `config/`) para (a) pedido de cadastro de
  navio/armador, (b) suporte remoto, (c) distributing `ATUALIZAR.command`.
- **Fase 2:** uma pasta compartilhada com `pacotes/`, `pedidos/`, `estado/` — dois sentidos.

## 9. Fases de implementação

| Fase | Entrega | Resultado |
|---|---|---|
| 0 | Baseline: commit do estado atual (o "botão de voltar") | repo com histórico |
| 1 | **Motor de lookups pelo popup** (seção 5) | a planilha aceita **nomes**; tabelas CSV viram fallback |
| 2 | Entrega por planilha: `C3` + `HISTÓRICO` + notificação + pasta fixa | operador só preenche e salva |
| 3 | Instalador macOS (`launchd`, `.command`, energia, pasta fora do iCloud) | roda no Mac sem terminal |
| 4 | Fila de pedidos + auto-update + backup do estado | operação sem depender do estagiário |
| 5 | (CODEBA, não este RPA) cadastro de navio/armador automatizado | automação nº 2 |

## 10. Fora de escopo

- **A correção manual na desatracação** (calados e ET/ETA/ETS revisados) **continua manual**,
  por decisão do usuário. Automatizá-la é um projeto à parte.
- Validação de ETA/ETS contra a data real: **não** — o "+3 dias" é previsão corrigida à mão.
- O cadastro de navio/armador no OpenPort é tarefa da CODEBA (automação nº 2), não deste RPA.
- Extração do PDF do anúncio: descartada (risco de erro silencioso em calado).

## 11. Riscos e perguntas em aberto

1. **Qual tela o OpenPort usa para cadastrar navio/armador?** (necessário para a automação nº 2)
2. O `sqlATTRIB` lista só "Ativos" — registro **inativo** no OpenPort não aparece no popup.
   Precisa ser um "pedido de reativação", não um bug.
3. A opção de installer `.command` depende de o macOS permitir execução de script baixado
   ("Segurança do Gatekeeper") — testar no Mac real antes de prometer ao operador.
4. O e-mail (fase 1) depende de uma credencial SMTP que a CODEBA pode prover — **a definir**.
5. O reconhecimento foi feito **somente no QAS**. O layout do popup em PROD foi confirmado só
   por indício (mesmos ids de campo). **Antes de usar em PROD, repetir a verificação de ids
   no PROD com uma anúncio de teste supervisionado.**

## Anexo A — evidência do reconhecimento (QAS, 21/10/2026)

Reconhecimento **read-only**, sem digitar nada nos formulários e sem acionar Gravar/Confirmar/
Verificar/Excluir: cópia do projeto em pasta temporária, `.env` apontado para QAS, assert de
ambiente, `HEADLESS=true`, monkeypatch de `browser.acionar` para bloquear as ações destrutivas.
Evidências em `%TEMP%\opencode\qas_recon\` (`recon.py` … `recon9.py`, `recon*.json`,
`screenshots\`). O repositório não foi alterado.
