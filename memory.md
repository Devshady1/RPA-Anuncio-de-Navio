# memory.md — RPA Anúncio de Navio (OpenPort / CODEBA)

> Raiz do projeto: pasta `rpa-anuncio-navio/` (onde este arquivo está).
> Em 15/10/2026 o projeto foi preparado para handoff: `.env` removido,
> geradores movidos para `ferramentas/` com caminhos relativos.
> Atualizado em: 02/10/2026. Ambiente de trabalho do usuário — **segurança máxima**:
> nada que abra browser sem autorização explícita; PROD como padrão de operação
> (testes QAS concluídos em 02/10/2026); QAS via `--ambiente qas`.
>
> **Contexto de quem usa:** o **agente marítimo não sabe mexer no OpenPort**.
> Ele preenche formulário/planilha; o robô opera o sistema. Todo campo que o
> agente não conhece de cabeça (código CODEBA) precisa ser resolvido por tabela.
>
> **DUV (decidido 02/10):** **DUV = número da viagem.** O agente **não informa**
> DUV. Não há leitura oficial separada.

## 1. O que é
RPA em Python + Playwright que preenche o **Cadastro/Anúncio de Navio (tela 2003)**
no OpenPort da CODEBA. Entrada via **JSON na raiz de `dados_rpa/`** (contrato no
README), **planilha-modelo** ou `wizard.py`; o runner `run.py --fila` consome a fila.
A interface **Streamlit (`app.py`) foi removida em 02/10/2026** — o novo método de
inserção de dados que o QA vai definir entra por esse mesmo contrato (JSON na raiz
de `dados_rpa/`), sem tocar no runner.

## 2. Arquitetura / arquivos
```
rpa-anuncio-navio/
  run.py                    # Runner: --interativo | --fila | --json | --dry-run | --status
                             #   + --ambiente qas|prod, --url, --dados-rpa, --manter-aberto
  monitor_fila.py           # Loop a cada 10s; chama run.py --fila (--simular = só validar)
                             #   É o seam da futura Torre RPA: vigia dados_rpa/ e dispara
  requirements.txt          # dependencias fixadas nas versoes testadas
  README.md                 # manual operacional para QA/torre de RPA
  .gitignore                # ignora .env, evidencias, fila processada e estado local
  tests/                    # unittest stdlib: fila_json + verificar (sem browser)
  modelo_anuncio_navio.xlsx # Planilha-modelo (Seção 0 do app importa .xlsx)
  memory.md                 # este arquivo
  # `.env` real removido no handoff (02/10/2026); recriar a partir de `.env.example`.
  .env.example              # modelo com QAS default + MANTER_ABERTO
  # `.env` real foi removido no handoff (02/10/2026): recriar a partir do exemplo.
  # `app.py` + `.streamlit/` (portal Streamlit) REMOVIDOS em 02/10/2026 — backup em
  #   %TEMP%\opencode\backup_streamlit_20261002\. Entrada agora é JSON em dados_rpa/.
  tabelas/                  # CSVs de referência: agencias, armadores, operadores, portos, cargas
                            #   cargas.csv = 966 linhas extraídas do PDF "LISTAGEM DE MERCADORIA"
  dados_rpa/                # fila: *.json pendentes | processados/ | duplicados/ | erro/ | pdfs/
  data/status.json          # anti-duplicidade {imo_viagem: {duv}}
  data/sequencia.json       # contador de viagem/DUV (proxima(), alinhar())
  src/anuncio_navio/
    config.py               # URL_QAS/URL_PROD, detectar_ambiente(), Config.ambiente, from_env(url_override)
    fila_json.py            # listar_pendentes, carregar_anuncio, normalizar (aliases),
                             #   finalizar_sucesso / finalizar_duplicado / finalizar_erro / finalizar_dryrun
    sequencia.py            # proxima(root) -> 000001,000002... ; atalhar(root); alinhar(root,min)
                             #   ATOMICA (tempfile+os.replace): o produtor pode rerodar e ler no meio
    planilha.py             # ler_planilha (por RÓTULO), validar_campos, construir_payload
    tabelas.py              # avisos_codigos (warning + sugestão difflib), descricao(), estrito=False
    browser.py              # preencher/selecionar/acionar, preencher_lookup (TAB→Enter→lupa-popup),
                            #   aceitar_dialogos (log + OK), screenshot
    anuncio.py              # criar_anuncio: blocos 1-4, DUV=viagem antes de Gravar,
                            #   Gravar→Verificar→Regravar→Confirmar(gated), DUV fallback=viagem
    navegacao.py            # login (retry 3x), abrir_tela_2003, abrir_tela_2001, novo_registro
    verificar.py            # confirmado_na_2001: filtra ETA/status, confere grade,
                            #   abre Modificar e valida cabecalho do cadastro (somente leitura)
    main.py                 # executar_um (log Ambiente, anti-duplicidade, relatorio)
    wizard.py               # modo interativo antigo (input()) — mantido como fallback
    status.py / relatorio.py / retry.py / exceptions.py
  logs/  screenshots/  relatorios/
```

## 3. Fluxo oficial
1. O método de inserção grava `dados_rpa/{IMO}_{VIAGEM}.json` na raiz — hoje via
   JSON manual, planilha-modelo (`planilha.py`) ou `wizard.py`; amanhã via o
   método do QA. **`fila_json.carregar_anuncio` é a fronteira do contrato.**
2. A **VIAGEM/DUV é reservada na emissão** (`sequencia.proxima` → 000001, 000002…),
   nunca sorteada. Gera avisos de código (tabelas anti-typo) na conferência.
3. `run.py --fila --dry-run` valida e arquiva em `processados/*__DRYRUN.json`
   (inválidos vão p/ `erro/` + `.log.txt`). **Dry-run consome a fila.**
4. Run real (`--json ... --ambiente qas` + `CONFIRMAR_ANUNCIO=1` p/ finalizar):
   login → 2003 → Novo → preenche → **DUV=viagem** → Gravar → Verificar →
   Regravar → Confirmar (auto-OK nos dialogs) → arquiva `*__DUV<duv>.json`.
5. `monitor_fila.py` automatiza o passo 4 em loop (**execução real** por padrão;
   `--simular` troca pelo passo 3, só validar).

## 4. Travas de segurança (NÃO remover sem avisar)
| Trava | Onde | Efeito |
|---|---|---|
| `--simular` | `monitor_fila.py::rodar_rpa` | opt-in; sem ele o monitor executa real (dry-run validado em §9.1) |
| Anti-PROD | `run.py::bloqueado_prod` | URL PRODUÇÃO sem `PERMITIR_PROD=1` → aborta exit 2 antes do browser |
| `MODO_PRODUCAO=1` (monitor) | `monitor_fila.py::rodar_rpa` | **removido** em 01/10/2026: redundante com `PERMITIR_PROD=1` do `run.py` (§8) |
| `CONFIRMAR_ANUNCIO=1` | `anuncio.py::criar_anuncio` | sem ela, para no Verificar (rascunho, não finaliza) |
| QAS default | `config.py URL_QAS`, `.env` | fallback e `.env` apontam homologação; PROD comentada |
| `Config.ambiente` | logado em todo run real | visível `Ambiente: QAS — <url>` antes de navegar |

## 5. O que foi feito (histórico)
1. Entrada `input()` → fila JSON `dados_rpa/` (`fila_json.py`, `run.py --fila/--json`).
2. `app.py`: 4 seções (identificação, ETs, operacional+4 calados, PDFs opcionais),
   validações (IMO 7 dígitos, calado ≤10, obrigatórios), expander classificação.
3. PDFs opcionais (`""` quando ausente, salvos em `dados_rpa/pdfs/` c/ prefixo IMO).
4. `monitor_fila.py` (10s, timestamp, nunca quebra).
5. Dry-run passou a **consumir a fila** (`__DRYRUN`) — acabou loop do monitor.
6. URL QAS + `--ambiente/--url` + trava anti-PROD (achado: `.env` estava em PROD!).
7. `app.py` alinhado à tela 2003 (ETB/ETC/ETS, portos, armador, operador, unidades, 4 calados).
8. `modelo_anuncio_navio.xlsx` profissional + `planilha.py` (leitura por rótulo).
9. `tabelas/` + conferência 2 etapas c/ descrições e avisos anti-typo.
10. Agências cadastradas: 30002 INTERMARIT, 30010 MARINAV, 30103 IRMÃOS BRITTO
    (30084 WILSONS SONS removida — é rebocador).
11. `cargas.csv` com **966 códigos de 8 dígitos** extraídos do PDF da listagem
    (achado: usávamos 6 dígitos — ex. `260400` → correto `26040000`).
12. Fallback lupa-popup (`preencher_lookup`: TAB→Enter→lupa→filtrar→selecionar).
    Corrigido bug que clicava a lupa da agência p/ outros campos.
13. Passo Confirmar (gated) + DUV=viagem preenchida antes do Gravar
    (achado via dialogs logados: `500021` + `Campo 'DUV' não pode ficar vazio`).
14. Handler persistente de dialogs (loga texto + OK; cobre beforeunload "Sair do site?").
15. Screenshot `anuncio_final` automático.
16. **[30/09] Viagem/DUV sequencial** (`sequencia.py`): `000001`, `000002`… reservation
    no momento do envio (`app.py::salvar_json`). DUV = viagem.
17. **[30/09] DUV nunca mais sorteada.** `random.randint` saiu de `anuncio.py`
    (havia gravado `DUV=99999`, `74628`, `59176` no histórico). Vazio agora é
    registrado como vazio, com aviso.
18. **[30/09] Duplicado ≠ sucesso**: vai para `dados_rpa/duplicados/` e conta como
    falha (`run.py`), em vez de sumir em `processados/` como sucesso.
19. **[30/09] `tabelas/navios.csv` limpo**: 401 → 241 linhas. Removidas 157 sem IMO
    e 3 com IMO inválido (`11111`, `971316`, `870999`). Backup: `navios.csv.bak`.
    Na base limpa a busca por nome/LOA funciona para todos.
20. **[02/10] Interface Streamlit removida** (`app.py` + `.streamlit/`; backup em
    `%TEMP%\opencode\backup_streamlit_20261002\`). A entrada passa a ser o **JSON em
    `dados_rpa/`**, documentado no README como **ponto de extensão** para o método de
    inserção que o QA vai definir (projeto vai integrar a uma Torre RPA). `streamlit`
    saiu do `requirements.txt`; `monitor_fila.py` já vigia a fila e é o seam natural.
21. **[13/10] Ingestão tolerante a encoding** (`fila_json._ler_texto_entrada`):
    tenta `utf-8-sig` (BOM, default de PowerShell 5.1/Notepad/.NET) e cai para
    `cp1252` (produtores legados). Antes, um JSON com BOM ia para `erro/` com
    "Unexpected UTF-8 BOM". Cobertura: `tests/test_fila_json.py` (BOM + cp1252).
    Só o ponto de entrada mudou; `status.py`/`sequencia.py` (internos) seguem utf-8.
22. **[14/10] Ficha do agente marítimo (`ficha_anuncio_navio.xlsx`)** — substitui o
    portal Streamlit removido: só células claras, ★ nos obrigatórios, linha STATUS
    com fórmula viva, ordem **navio → viagem → carga/calado → responsáveis**.
    **O agente só escreve NOMES**: agência/armador/operador/afretador/portos
    resolvem nome→código (`tabelas.resolver` + entrada `afretador` no MAPA, que
    antes quebrava com `PermissionError`), e passa a valer também para a **carga**.
23. **[14/10] Carga passa a ser resolvida por nome** — decisão do usuário (o agente
    não sabe código; é dever do RPA). `tabelas.resolver_carga()`: comparação por
    palavras (ignora acento/caixa/plural), e **prefere o minério** (`MINERIO/
    CONCENTRADO/BRUTO`) porque navio não opera sulfato/catalisador/resíduo — isso é
    saída de balança. Resolve sozinho só quando sobra **um** código (`cromo` fica
    ambíguo entre cromita e outros minérios; `soja`/`café torrado` também pedem
    escolha humana). A regra que não mudou: **nunca adivinha**.
24. **[14/10] Classificação não é mais perguntada** — `config.CLASSIFICACAO_PADRAO`
    aplica `1/1/1/1` (longo curso / mov. de carga / exportação / sólido) quando
    vier vazia, na leitura da ficha e no `fila_json.normalizar`. Correção manual
    quando a operação for diferente.
25. **[14/10] Teto de calado: 16 m** (`planilha.CALADO_MAX_M`) — regra do PORTO,
    não do navio. Navio com calado máximo menor segue exigindo conferência manual
    (ex.: TI SUNRISE, 10,527 m no summer).
26. **[14/10] Buraco conhecido em `cargas.csv`:** não existe código NCM `2601*`
    (minério de ferro) na base de 966 linhas. Quando o minério for cadastrado no
    OpenPort, o usuário passa o código para entrar na tabela — sob demanda.
    Ferro é o único caso conhecido; níquel, manganês, cromo e cobalto existem.
27. **[15/10] Entrada autônoma (`entrada/`)** — o anúncio deixou de depender de
    conversa: o agente salva a ficha preenchida em `entrada/` e o
    `monitor_fila.py` converte sozinho (`inserir.ingerir_pendentes`) antes de
    disparar o RPA. Ordem crítica: a planilha **sai de `entrada/` antes** de
    validar/reservar viagem, então ficha aberta no Excel não duplica JSON nem
    queima número (fica para o ciclo seguinte). Ficha rejeitada → `entrada/erro/`
    com `.log.txt`; aprovada → `entrada/processados/`.
    Bugs achados e corrigidos na volta: `planilha.ler_planilha` não fechava o
    workbook (`read_only`) e travava o arquivo no Windows; `MAPA` sem `afretador`.
    Cobertura: `tests/test_inserir.py` + `tests/test_limpeza.py`.
28. **[15/10] Resíduo/desperdício bloqueado** (`tabelas._TOKENS_DESPERDICIO`):
    navio nunca opera cascas/resíduos/refugo (saída de balança) — o RPA se recusa
    a devolver esses códigos, inclusive quando digitados na mão.
29. **[15/10] Cacau fixo 18010000** (`tabelas.CODIGO_FIXO_CARGA`) — confirmado
    pelo usuário; apelidos comerciais (`APELIDOS_CARGA`) traduzem a fala do porto
    ("amêndoa de cacau") para o termo da NCM. Crescem sob demanda.
30. **[15/10] Purge de evidências** (`limpar_evidencias.py`) — remove
    `relatorios/`, `screenshots/` e `logs/` com mais de N dias (padrão 30).
    Dry-run por padrão: só `--executar` apaga. Preserva `run_audit.bat`.
31. **[15/10] Preparado para handoff/repositório** — `.env` (com credenciais)
    removido conforme pedido; `.gitignore` passa a versionar
    `data/status.json` e `data/sequencia.json` (sem eles um clone novo voltava o
    contador de viagem para `000001` e colidia com os anúncios já feitos);
    `reportlab` fixado no `requirements.txt`; os 3 geradores que estavam em
    pasta temporária foram para `ferramentas/` com caminhos relativos
    (`gerar_ficha.py`, `relatorio_prod.py`, `relatorio_executivo.py`);
    `entrada/` com `.gitkeep`; README ganhou a seção "Para quem está assumindo".
    Varredura de credenciais: nenhum vestígio no projeto (só os placeholders do
    `.env.example`).     Evidências (`logs/`, `screenshots/`) seguem fora do repo por decisão.
    Decisão fina sobre `relatorios/`: **só o PDF executivo é versionado**
    (`relatorios/*` + `!relatorios/RELATORIO_EXECUTIVO_*.pdf` — precisa ser `/*`
    porque git não re-inclui arquivo dentro de diretório excluído). O relatório
    detalhado e os `.log` de rodada ficam fora. `logs/run_audit.bat` apagado
    (tinha caminho absoluto da máquina antiga). Regras conferidas com
    `git check-ignore`.

## 6. Estado atual (28/09/2026)
- ✅✅ **VOYAGER (IMO 9553256): ANÚNCIO CONFIRMADO de ponta a ponta no QAS**
  ("Anúncio confirmado com sucesso.", Status=Confirmado, **Programação 1770**,
  Data registro 28/09/2026 16:28, calados 8,30, carga 260400 NÍQUEL).
  Correções que destravaram: DUV=viagem preenchida antes do Gravar,
  calados com vírgula, ETs futuras (ETA>data atual, erro 60133).
- Fila: `1234567_0000000.json` (teste tautuatu, pendente).
- ~~Streamlit: cai com frequência~~ → interface removida (02/10); não há mais UI local.
- MSC ARMONIA (9210141): processado c/ pendências (agência/carga não existiam no backup).

## 7. Erros conhecidos e causa
| Erro | Causa | Status |
|---|---|---|
| `Carga 260400 não resolve` | código de 6 dígitos; correto tem 8 (`26040000`) | ✅ resolvido |
| Lupa abria `LISTAGEM DE AGENTES` p/ carga | fallback usava `agencia_lupa` p/ todos os campos | ✅ resolvido |
| `500021; necessário gravar antes de completar/confirmar` | Verificar invalida o save; faltava regravar + DUV vazia | ✅ resolvido (regravar + DUV=viagem) |
| `Campo 'DUV' não pode ficar vazio` | robô nunca preenchia a DUV | ✅ resolvido (DUV=viagem antes do Gravar) |
| Monitor reprocessava mesmo arquivo | dry-run não consumia a fila | ✅ resolvido (`__DRYRUN`) |
| Shell do harness mata processos longos/`Start-Process` (`ChildProcess.kill`) | limitação do ambiente de execução | ⚠️ contorno: `schtasks` p/ runs c/ auditoria aberta |
| Excel aberto trava regeneração do modelo | lock do arquivo | ⚠️ fechar o Excel antes |
| Streamlit cai sozinho | sem supervisão | ✅ resolvido: interface removida (02/10) |
| JSON com BOM ia p/ `erro/` (`Unexpected UTF-8 BOM`) | leitura só em `utf-8` | ✅ resolvido (13/10): `utf-8-sig` + fallback `cp1252` |

## 8. Decisões do usuário (30/09/2026)
- **DUV é número do sistema**, não aparece em papel → agente não informa nada.
- **Todos os navios terão IMO válido na base** a partir de 30/09 → é por isso que
  as 157 linhas sem IMO foram removidas em vez de tentadas recuperar.
- **Interface = formulário Streamlit** (não Google Form). Redesenhada em 01/10/2026
  para o agente que não consegue operar o OpenPort: busca de navio ao vivo,
  tabelas resolvem nome→código, um botão de envio, conferência antes de mandar.
  **[SUPERADO 02/10/2026]** — Streamlit removido; a conferência/validação migrou
  para o contrato JSON (`tabelas.resolver` + `planilha.validar_campos`).
- **`--dry-run` não é mais o padrão do monitor** (01/10/2026). O monitor executa
  **real**; simulação virou a flag opt-in `--simular`. A trava anti-PROD continua
  independente no `run.py` (`PERMITIR_PROD=1`), então ligar o monitor não libera
  produção. `MODO_PRODUCAO` foi removido do monitor por ser redundante.
- **Nome/descrição pode ser corrigido por tabela; calado e carga NUNCA** — erro
  de calado manda o navio para o porto errado.
- **PDFs fora do escopo (02/10/2026)** — o RPA não fará upload/envio de PDFs.
- **Operadores sob demanda (02/10/2026)** — o que for preenchido já está no
  OpenPort; se algum código travar, o usuário informa os códigos.
- **Campos restantes da 2003 são opcionais para o fluxo atual (02/10/2026)** —
  Escala, Janela, Data Anúncio, Amarração, Faturamento e Observação não impedem
  o anúncio confirmado no cenário validado.
- **Pronto para QA/torre (02/10/2026)** — README operacional, testes `unittest`,
  dependências fixadas, `.gitignore`, fila reconciliada e evidências padronizadas.
- **Produção como padrão (02/10/2026)** — testes QAS aprovados; `URL_PADRAO = PROD`.
  As travas continuam: sem `PERMITIR_PROD=1` o navegador não abre em produção.

## 9. Pendências conhecidas
- `run.py --fila --dry-run` ainda **consome** a fila (move p/ `__DRYRUN`). Para rodar
  de verdade depois, mover o arquivo de volta para `dados_rpa/`.
- `data/status.json` ainda tem as 2 entradas antigas com viagem `0000000` (histórico
  do bug). Não colidem com as novas (`000001`+), mas podem ser apagadas quando quiser.

## 9.1 Teste QAS de referência (01/10/2026)
Anúncio real confirmado em homologação:
- VOYAGER · IMO `9553256` · viagem `000001` · DUV `000001`
- Resultado: **"Anúncio confirmado com sucesso."**
- `dados_rpa/processados/9553256_000001__20260930_154502__DUV000001.json`
- Log `logs/teste_000001.log` · relatório `relatorios/rodada_015_*.log` ·
  screenshot `screenshots/anuncio_final_20260930_154501.png`
- Aviso `500021` ("gravar antes de completar/confirmar") apareceu no Regravar e foi
  julgado **não bloqueante**: o anúncio foi confirmado. Não pursue esse aviso.

## 9.2 O que mudou na interface (01/10/2026) — [histórico; UI Streamlit removida em 02/10]
Validado com `streamlit.testing.v1.AppTest` (sem browser; o harness mata
`Start-Process`, ver §7):
- `tabelas.resolver(campo, texto)` — heurística em 4 degraus: código exato →
  descrição igual normalizada (sem acento/caixa/espaço) → prefixo/contido →
  `difflib`. Carga só resolve por código exato, de propósito.
- `planilha.ler_planilha()` resolve nome→código igual ao formulário, e aceita
  classificação por nome (`LONGO CURSO` → `1`).
- `app.py::validar_datas()` — trava ETA ≤ ETB ≤ ETC ≤ ETS (não havia validação).
- Busca de navio **fora** do `st.form`: dentro do form o Streamlit não re-renderiza
  por tecla e o selectbox de resultados nunca aparecia.
- `modelo_anuncio_navio.xlsx` — rótulos "nome ou código", ajuda corrigida (passo 4/5/6).

## 9.3 Teste QAS de verificação 2001 (02/10/2026)
- VOYAGER · IMO `9553256` · viagem `000002` · DUV `000002`
- Criado e confirmado: **"Anúncio confirmado com sucesso."**, Programação **1772**.
- `verificar.confirmado_na_2001()` filtra ETA `05/10/2026` + status `Anunciado`,
  localiza a grade, abre **Modificar** e valida o cabeçalho do cadastro.
- Resultado isolado: **`RESULTADO_2001=CONFIRMADO`**.
- Achado: o cabeçalho da tabela está no `thead`; a primeira `tr` do `tbody` é dado.
- Pendência de reconciliação: esse JSON caiu em `erro/` pelo bug inicial do parser
  e `status.json` ainda não tem `9553256_000002`. Não reprocessar sem reconciliar.

## 9.4 Limites conhecidos do resolvedor
- `operadores.csv` está mínimo por decisão: completar somente sob demanda.
- Carga **exige código de 8 dígitos** por decisão (evita mercadoria errada).
- Corte fuzzy 0.80 pode chamar atenção em nomes muito curtos; revisar se aparecer.

## 9.5 Teste QAS de revalidação (02/10/2026)
- VOYAGER · IMO `9553256` · viagem `000004` · DUV `000004` (clone do `000003`).
- Resultado: **"Anúncio confirmado com sucesso."**, Programação **1774**,
  ETA `05/10/2026`, Status=`Anunciado`; `verificar` → `Confirmado na 2001 ... DUV_ref=000004`.
- Evidência: `logs/run_000004.log`, `screenshots/anuncio_final_20261002_170013.png`,
  `screenshots/verificacao_2001_ok_20261002_170034.png`.
- Achado: o harness matou o processo durante o `--manter-aberto` (60s de auditoria),
  **após** o anúncio confirmado mas **antes** de `finalizar_sucesso` mover o JSON.
  Reconciliado à mão: `dados_rpa/9553256_000004.json` →
  `dados_rpa/processados/9553256_000004__20261002_170013__DUV000004.json` (sem tocar o QAS).
  Lição: em smoke de `--manter-aberto`, conferir se o arquivo saiu da raiz de `dados_rpa/`.
- Viagem `000005` (VOYAGER, gerada 13/10 p/ e2e offline): só rodou `--dry-run`;
  descartada a pedido do usuário sem run real (backup em `%TEMP%\opencode\`).
  Número queimado, sem entrada no `status.json`.

## 9.6 Primeiro anúncio em PRODUÇÃO (13/10/2026)
- TI SUNRISE · IMO `9701009` · viagem `000006` · DUV `000006` (JSON montado do
  Ship Particulars + dados da viagem informados no chat).
- Resultado: **"Anúncio confirmado com sucesso."**, Programação **1772**,
  ETA `16/10/2026`, Status=`Anunciado`; `verificar` → `Confirmado na 2001`.
- Evidência: `logs/run_000006_prod2.log`, `screenshots/anuncio_final_20261013_162127.png`,
  `screenshots/verificacao_2001_ok_20261013_162147.png`, `relatorios/`.
- Achados PROD (diferenças vs QAS):
  - **Só CÓDIGO resolve via TAB em PROD.** Nomes (`marinav`, `intermarit`) falharam
    no TAB e a lupa-popup não salvou (agência: popup abriu mas "resultado nao
    selecionavel"). Com códigos (`30010`, `30002`) tudo resolveu de primeira.
  - Afretador com o código novo `00000000000005` (TAMAR, recém-cadastrado em PROD)
    falhou na 1ª tentativa e passou na 2ª sem mudança — flake de timing, não de dado.
  - 1ª tentativa parou no Regravar ("Armador Afretador não pode ficar vazio") e deixou
    rascunho DUV=000006; a 2ª (só trocando nomes→códigos) confirmou. Mesmo `viagem`
    reutilizada sem conflito.
- Pós-anúncio (responsabilidade do usuário): calados de saída `10/4` são placeholder
  (chegada `10/4` afirmada pelo usuário; `14` m original foi recusado — acima do máximo
  10,527 m) e ETB/ETC/ETS `19/10` pela regra +3 dias — correção manual prevista.

## 10. O que falta p/ rodar liso (TODO priorizado)
0. ✅ **Resolvido em 02/10** — `9553256_000002` reconciliado: entrada criada no
    `status.json` e JSON movido de `erro/` para `processados/` sem tocar no QAS.
1. ✅ **Resolvido em 02/10** — DUV = viagem foi aceita pelo OpenPort no teste QAS.
2. **Lupa-popup ainda não validada de ponta a ponta** — após o acerto do código de 8
    dígitos, tudo resolveu via TAB; falta um caso real que exija o popup.
3. ✅ **Resolvido em 02/10** — fim do "OK" incondicional: `executar_um` só chama
    `status.marcar_ok()` após `verificar.confirmado_na_2001()` retornar True.
4. **Filtro de duplicidade** — agora sequencial resolve o caso comum, mas se o agente
    reenviar o mesmo `{IMO}_{VIAGEM}` (mesmo arquivo) ainda barra. Considerar `--forcar`.
5. **`tabelas/` sob demanda** — completar somente se algum código legítimo travar.
6. ✅ **Resolvido em 02/10** — Streamlit removido; a "estabilidade" deixou de ser
    problema (não há mais UI para cair). `monitor_fila.py` já vigia a fila.
6b. **Novo método de inserção (QA) / Torre RPA** — o supervisor do usuário dará o
    passo a passo; integrar pelo contrato JSON em `dados_rpa/` (ver README, §3).
7. **[REMOVIDO][02/10] Leitura de DUV oficial** — decisão atual: DUV = viagem.
8. **[FORA DO FLUXO ATUAL][02/10] Cobertura total da 2003** — Escala, Janela,
    Data Anúncio, Amarração, Faturamento e Observação não são exigidos para o
    anúncio confirmado no cenário validado.
9. **[FORA DE ESCOPO][02/10] PDFs** — sem upload/envio por decisão do usuário.
10. **Limpeza**: `screenshots/` e `relatorios/` acumulam — rotina de purge (>30 dias).
11. **Credenciais locais** — o `.env` real foi removido do pacote no handoff;
    recriar a partir do `.env.example`. O `.gitignore` cobre `.env`.
12. ✅ **Resolvido em 01/10** — `tabelas.resolver()` trata nome, código, acento,
    caixa, espaço e typo (`MARINAVV` → `30010`) nos campos de tabela, tanto no
    formulário quanto na planilha. Carga permanece só por código.

## 11. Comandos úteis
```powershell
cd rpa-anuncio-navio
python run.py --fila --dry-run --ambiente qas # valida fila (consome p/ processados)
python run.py --json dados_rpa\<IMO>_0000000.json --ambiente qas   # run real (rascunho)
$env:CONFIRMAR_ANUNCIO="1"; python run.py --json dados_rpa\<IMO>_0000000.json --ambiente qas --manter-aberto  # full + auditoria sem fechar o navegador
python run.py --status
python monitor_fila.py --uma-vez --simular   # teste do monitor sem abrir browser
```

## 12. Modelo Excel oficial e identidade
- Oficial: Exemplo_Interface_CODEBA_QAS como modelo_anuncio_navio.xlsx (23 validacoes, STATUS, nomes Lista*, institucional, ja vinha com 1 imagem).
- ATENCAO: gerar_modelo.py (TEMP) DEPRECIADO — regenerar apaga o oficial! Excel = edicao cirurgica.
- portos.csv = 25.456 do QAS (portal busca mundo, BR primeiro); Catalogo do Excel = 102 BR (ListaPortos A23:A124; dropdown gigante e inutilizavel).
- Logo: logo_codeba.png (JPEG fundo xadrez falso) -> logo_codeba_transp.png (alpha real; texto branco = uso sobre fundo escuro).
- Portal Streamlit (`.streamlit/config.toml`, tema dark navy) REMOVIDO em 02/10/2026 junto com `app.py`.
