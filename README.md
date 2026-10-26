# RPA Anúncio de Navio — OpenPort/CODEBA

Robô para anunciar navios na tela 2003 e confirmar o aceite na tela 2001.

> **A interface Streamlit foi removida em 02/10/2026.** O ponto de entrada
> de dados é o JSON em `dados_rpa/` (ver *Inserção de dados*). O espaço do
> portal fica reservado para o novo método de inserção que o QA vai definir
> — ver *Ponto de extensão*, que descreve o contrato a respeitar.

## Para quem está assumindo o projeto (handoff)

1. **Estado:** anúncio validado em QAS e o **primeiro anúncio em produção feito
   em 13/10/2026** (TI SUNRISE, viagem 000006, programação 1772). Registro
   completo em `memory.md` §9.6.
2. **Antes de rodar:** copie `.env.example` para `.env` e preencha
   `OPENPORT_LOGIN` / `OPENPORT_SENHA` — sem isso o robô aborta antes de abrir
   o navegador. O `.env` **não** vai para o repositório (está no `.gitignore`).
3. **Ambiente:** `.env` define a URL (padrão = PRODUÇÃO). Para homologação use
   `--ambiente qas`. Produção exige `PERMITIR_PROD=1` **e** `CONFIRMAR_ANUNCIO=1`.
4. **Não apague `data/sequencia.json`:** é o contador de viagem/DUV. Sem ele o
   primeiro anúncio recomeça em `000001` e colide com o que já existe no sistema.
5. Rode os testes antes de alterar qualquer coisa:
   `python -m unittest discover -s tests`.
6. **Pendências e decisões:** `memory.md` (§5 histórico, §9 achados, §10 o que
   falta). O fluxo de entrada autônoma está em §27–30.
7. `ferramentas/` guarda quem gera a ficha e os relatórios em PDF
   (`python ferramentas/gerar_ficha.py`). Os caminhos são relativos ao projeto.

## Fluxo

1. O método de inserção grava `dados_rpa/{IMO}_{VIAGEM}.json` na raiz de `dados_rpa/`.
2. `run.py --fila` executa: login → 2003 → preencher → Gravar → Verificar → Confirmar.
3. `verificar.confirmado_na_2001()` filtra ETA/status, abre **Modificar** e valida o cadastro.
4. `status.marcar_ok()` só acontece após confirmação real.

## Ficha do agente marítimo (não depende de ninguém no chat)

```
ficha_anuncio_navio.xlsx  ->  entrada/  ->  inserir.py  ->  dados_rpa/{IMO}_{VIAGEM}.json  ->  RPA
```

- O agente preenche a ficha **só com nomes** e salva em `entrada/`.
- `python inserir.py entrada` converte a ficha em JSON (resolvendo códigos e
  reservando a viagem), ou o `monitor_fila.py` faz isso sozinho a cada ciclo.
  Na conversão, o texto do agente vai intacto e o código do CSV local (quando
  existe) viaja ao lado, como fallback — a resolução final é do popup do
  OpenPort, no momento do anúncio.
- A ficha convertida vai para `entrada/processados/`; a rejeitada para
  `entrada/erro/` com `.log.txt` dizendo o motivo. Ficha ainda aberta no Excel
  fica em `entrada/` e é reprocessada no ciclo seguinte (nunca duplica).
- `python consulta_carga.py <mercadoria>` consulta o código NCM antes de preencher.

## Comandos

## Inserção de dados

O contrato é **um arquivo JSON por anúncio, na raiz de `dados_rpa/`**
(subpastas `processados/`, `erro/`, `duplicados/`, `pdfs/` são do robô).

- Nome sugerido: `{IMO}_{VIAGEM}.json` (ex.: `9553256_000004.json`).
- Consumidor: `fila_json.carregar_anuncio()` (aceita aliases de campo e normaliza)
  via `run.py --fila`.
- Saída: sucesso → `processados/`; inválido/erro → `erro/` (+ `.log.txt`);
  já anunciado → `duplicados/`.
- Exemplo real preenchido: `dados_rpa/processados/9553256_000004__*__DUV000004.json`.

Campos esperados (resumo): `nome_navio`, `imo`, `viagem`, `agencia`, `armador`,
`operador`, `porto_ant`, `porto_prox`, `berco`, `afretador`, `carga` (nome da
mercadoria **ou** código NCM de 8 dígitos — quem resolve é o popup do OpenPort;
o CSV local é fallback),
`qtd`, `tons`, `loa`, `tpb`, `eta/etb/etc/ets` (`DD/MM/AAAA HH:MM`, futuras),
`calado{chegada_proa,chegada_popa,saida_proa,saida_popa}`, `documentos{dpem,manifesto,tripulantes}`,
`tipo_viagem`, `tipo_operacao`, `sentido`, `natureza` (padrão `1/1/1/1` quando
omitidos).

## Ficha do agente marítimo

`ficha_anuncio_navio.xlsx`. O agente preenche só nomes — agência, armador,
operador, afretador, portos, berço e **carga** podem ser escritos por **nome ou
código**. A resolução é feita pelo **popup de consulta do OpenPort** (fonte viva
do cadastro): o texto do agente vai intacto, o popup devolve o código e a
seleção preenche o campo. O CSV em `tabelas/` é só **fallback**, usado quando o
popup não conhece o cadastro. Nome ambíguo **não é adivinhado**: o RPA barra
antes do Gravar e lista os candidatos.

## Ponto de extensão (para o QA)

O novo método de inserção **não precisa tocar no runner**: basta escrever
JSONs válidos na raiz de `dados_rpa/` (o `monitor_fila.py` dispara sozinho, ou
rode `run.py --fila`). Regras a respeitar:

- **`viagem`/DUV precisa ser único por navio.** Reserve via
  `anuncio_navio.sequencia.proxima(root)` (atômico) antes de gravar o JSON —
  a anti-duplicidade (`status.json`, chave `imo_viagem`) barra repetição.
- **Lookups por nome ou código**: agência, armador, operador, afretador, portos,
  berço e carga são resolvidos pelo popup do OpenPort; o que o RPA não resolve
  **barra antes do Gravar** (com os candidatos na mensagem). Calado nunca é
  adivinhado (erro manda o navio ao porto errado).
- **Carga**: nome da mercadoria ou código NCM de 8 dígitos; pelos dois caminhos
  ela não é adivinhada — ambígua barra com os candidatos.
- **ETs no futuro** (ETA ≤ ETB ≤ ETC ≤ ETS), senão o OpenPort recusa (erro 60133).
- **Encoding do arquivo**: aceita UTF-8 com ou sem BOM (`utf-8-sig`) e `cp1252`,
  para não quebrar com a ferramenta que o produtor usar. Grave `utf-8` quando puder.

## Comandos

```powershell
python -m unittest discover -s tests -v
python run.py --fila --dry-run --ambiente qas
python run.py --json dados_rpa\<IMO>_<VIAGEM>.json --ambiente qas
$env:CONFIRMAR_ANUNCIO="1"; python run.py --json dados_rpa\<IMO>_<VIAGEM>.json --ambiente qas --manter-aberto
python run.py --status
python inserir.py entrada            # converte as fichas da pasta de entrada
python consulta_carga.py niquel      # nome da mercadoria -> codigo NCM
python monitor_fila.py --uma-vez --simular
python limpar_evidencias.py          # lista evidencias com mais de 30 dias
python limpar_evidencias.py --executar
```

## Métodos de entrada atuais

- **JSON manual / integrador externo** — contrato acima (caminho principal).
- **Planilha-modelo** `modelo_anuncio_navio.xlsx` via `planilha.ler_planilha()` +
  `construir_payload()` (sem UI: exige pequeno wrapper de CLI).
- **`wizard.py`** — modo interativo por terminal (fallback antigo).

## Segurança

- Produção é o destino padrão (testes de QAS concluídos em 02/10/2026).
- Produção exige `PERMITIR_PROD=1`, senão o navegador nem abre.
- Use `--ambiente qas` para voltar à homologação.
- `CONFIRMAR_ANUNCIO=1` é exigido para finalizar.
- `.env` não deve ser versionado.
- Evidências ficam em `relatorios/`, `screenshots/` e `dados_rpa/`.

## Falhas

- JSON inválido ou falha de execução vai para `dados_rpa/erro/` com `.log.txt`.
- Duplicado vai para `dados_rpa/duplicados/`.
- Sucesso vai para `dados_rpa/processados/`.
- `--dry-run` consome a fila sem anunciar.

## Ficha única — serviço em desenvolvimento (Plano A)

Além do fluxo legado `entrada/` → JSON, existe o modo opt-in `--servico`, que
observa uma única ficha em `ficha/ficha_anuncio_navio.xlsx`. O serviço ainda
está em validação; o instalador e a configuração de inicialização automática
do macOS são um Plano B separado e **não estão implementados neste repositório**.

Layout usado pelo serviço sob `ANUNCIO_ROOT`:

```text
<root>/
  ficha/ficha_anuncio_navio.xlsx
  ficha/arquivo/                 # fichas processadas
  data/                          # status, sequência, histórico e pedidos
  data/json/                     # JSON de evidência/contrato
  logs/servico.log
  logs/servico.lock
  tmp/                           # reservado no layout de deploy
  config/.env                    # configuração local do serviço
```

Em desenvolvimento, `ANUNCIO_ROOT` pode apontar para uma pasta temporária.
O primeiro ciclo cria uma ficha em branco se ela não existir; a ficha só pode
ser lida depois de ficar estável por cinco segundos. Para fazer um smoke test
de criação sem abrir o navegador:

```powershell
$root = Join-Path $env:TEMP ("anuncio-navio-smoke-" + [guid]::NewGuid().ToString("N"))
$env:ANUNCIO_ROOT = $root
python monitor_fila.py --servico --uma-vez
```

Regras do ciclo:

- Ficha incompleta ou falha: o arquivo permanece na pasta com o motivo em
  `STATUS`; uma ficha inalterada não é tentada novamente.
- Sucesso: a ficha preenchida é arquivada e uma nova ficha em branco é criada.
- Duplicado pelo mesmo IMO e ETA: é arquivado sem anunciar novamente.
- A ficha deve estar salva e fechada antes do processamento.

O smoke test acima não acessa o OpenPort. A primeira validação ponta a ponta
do serviço foi executada no QAS em 26/10/2026: o anúncio de teste IMO 9553256,
viagem/DUV 009999, ETA 20/11/2026 foi confirmado e localizado na tela 2001
(programação 1781, status `Anunciado`). A execução usou `CONFIRMAR_ANUNCIO=1`,
pois a verificação padrão só considera sucesso quando encontra esse status.
Esse registro foi persistido no QAS; não reutilize a mesma viagem/ETA para
repetir o teste.
