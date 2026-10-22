# Desenho — entrega no Mac do agente: ficha única, serviço invisível

**Data:** 2026-10-22 · **Status:** proposta para aprovação · **Escopo:** fases 2 e 3 do
`2026-10-21-entrega-macos.md` (esta entrega por planilha + instalador macOS)
**Substitui, para o escopo acima:** decisões 1–6 da seção 3 e seções 6–8 da spec original.

---

## 1. Intenção e por que

O RPA (fase 1, mergeada em `master`, tag `v0.1.0-fase1`) já resolve os 8 lookups pelo popup do
OpenPort e anuncia de ponta a ponta. O que falta é a **entrega**: o agente marítimo — pessoa idosa,
pouco familiarizada com sistemas — não pode abrir terminal, copiar arquivo, renomear nem olhar
console. O MacBook é pessoal dele; a instalação e as atualizações são feitas por uma única pessoa
(o estagiário/autor) com privilégios de administrador.

O valor está em transformar o robô num **serviço invisível com a planilha como única interface**:
ele preenche a ficha com os nomes que conhece, salva, e recebe o resultado — certo ou errado —
sem aprender nada novo.

## 2. Objetivo e critério de sucesso

Sucesso = em qualquer momento em que ele abrir a pasta, existe **exatamente uma ficha em branco**
esperando; ele preenche, `Cmd+S`, fecha; em até ~2 min o anúncio é gravado e confirmado em PROD e
ele recebe uma notificação do macOS; a ficha preenchida foi arquivada e uma nova em branco está no
lugar. Se algo falhar, **nada é perdido**: a planilha fica no lugar com o motivo escrito.

## 3. Não-objetivos e anti-objetivos

- **Não-objetivos:** e-mail/SMTP, auto-update, fila de pedidos distribuída, backup remoto, cadastro
  automatizado de navio/armador (fase 5), segundo operador/máquina, roda em servidor.
- **Anti-objetivos** (seria fracasso mesmo funcionando): anunciar o navio errado em silêncio;
  perder o que o operador digitou; exigir terminal do agente; anunciar de teste em PROD; deixar o
  `status.json`/`sequencia.json` sem cópia enquanto o DUV é consumido.

## 4. Fatos e restrições

- macOS pessoal do agente, **acesso de administrador** para o instalador (o agente não é).
- O agente **nunca** abre Terminal; toda ação dele é duplo clique ou edição da planilha.
- Credencial do OpenPort = **conta do próprio agente**, com permissão de anunciar (confirmado).
  Ele digita a senha uma vez, na própria máquina; o instalador não precisa conhecê-la.
- Instalado, já aponta para **PROD** (`PERMITIR_PROD=1`, `CONFIRMAR_ANUNCIO=1`). PROD não é teste:
  nenhum anúncio fictício; a verificação pós-instalação é **read-only** (login + telas).
- Estado é local à máquina (`status.json` anti-duplicidade, `sequencia.json` DUV); um agente, um Mac.
- O app de planilha do agente **é desconhecido** até a instalação: o instalador detecta Excel;
  se não houver, instala LibreOffice (Numbers não serve: `Cmd+S` salva `.numbers`, não o `.xlsx`).
- Rede do Mac precisa alcançar `openportilheus.codeba.gov.br` (validar no smoke test).

## 5. Decisões

### 5.1 Decididas pelo usuário

1. Instalação e atualizações feitas por ele, com admin; o agente nunca instala nada.
2. Ao instalar, já é produção; credencial é a do agente, digitada por ele.
3. Padrão da pasta: **sempre uma ficha** — após sucesso, arquivar a preenchida e gerar uma nova em
   branco; após falha, deixar a mesma no lugar para correção.
4. Nomes (não códigos) são a entrada principal; ambiguidade barra antes do Gravar.

### 5.2 Chamadas do construtor (podem ser questionadas, mas não bloqueiam)

1. **Runtime embutido** em vez de Python de sistema: `python-build-standalone` (CPython 3.12)
   descompactado em `app/runtime/`, dependências pré-instaladas e Chromium do Playwright em
   `app/runtime/browsers/` (`PLAYWRIGHT_BROWSERS_PATH`). Dois payloads (arm64 e x86_64), escolhidos
   no `uname -m`. Nada de Python global, nada de `pip install` na máquina do agente, nada de sudo
   para Python.
2. **Senha no Keychain** (`security add-generic-password -s com.codeba.anuncionavio.openport`), não
   em arquivo. `config/.env` guarda só o não-secreto (URL, flags, login).
3. **`CONFIGURAR.command`**: diálogos nativos `osascript` (`hidden answer` para a senha), grava no
   Keychain e reescreve o `config/.env`; também usado quando a senha muda.
4. **Serviço** `LaunchAgent` `com.codeba.anuncionavio` em `~/Library/LaunchAgents/`, `RunAtLoad` +
   `KeepAlive`, executando `caffeinate -s <runtime>/bin/python3 monitor_fila.py --servico`
   (`caffeinate -s` evita suspensão ociosa na tomada). Tampa fechada: o instalador oferece
   `sudo pmset -a disablesleep 1` (reversível) ou só a instrução "deixe aberto na tomada" — escolha
   na instalação; sem `disablesleep`, o robô espera a tampa abrir e processa (nada se perde).
5. **Notificação** via `osascript -e 'display notification …'` (o LaunchAgent roda na sessão do
   usuário, então aparece).
6. **`C3` é a única linha de status**: enquanto ele preenche, é a fórmula de validação ao vivo
   ("OK — PRONTO PARA ENVIAR" / "FALTAM N CAMPOS"); na falha, o robô **escreve o veredito na
   própria `C3`** (a fórmula volta com a ficha nova em branco, que é gerada após sucesso). A faixa
   é **mesclada `C3:E3`**, com quebra de linha e altura para mensagens longas (ex.: candidatos
   ambíguos). O robô também acrescenta linha no `HISTÓRICO` e notifica. A aba `COMO PREENCHER` e a
   linha 29 passam a dizer "Salve (Cmd+S) e feche; a ficha nova aparece sozinha".
7. **`HISTÓRICO` mestre** em `data/historico.csv` (append-only); a cada ficha nova, a aba é
   regerada com todas as linhas — o arquivo não acumula histórico dentro de si.
8. **Ficha nova** = cópia do modelo `app/recursos/ficha_modelo.xlsx`, derivado da
   `ficha_anuncio_navio.xlsx` (abas `Anúncio` + `COMO PREENCHER`, `C3:E3` mesclada e a aba
   `HISTÓRICO`). A `modelo_anuncio_navio.xlsx` (Catálogo/Ajuda) é demo de importação no portal e
   **não** entra no fluxo do agente. Evidência = a ficha preenchida, arquivada com timestamp e DUV.
   Exemplo visual do estado de falha: `docs/superpowers/specs/exemplos/ficha_com_falha.xlsx`.
9. **Planilha**: se `Microsoft Excel.app` existe, é o padrão; senão instalar LibreOffice do pacote e
   criar `Ficha de Anúncio.app` (AppleScript) na Área de Trabalho que faz `open -a LibreOffice`.
   Sempre com atalho de pasta "Anúncio de Navio" → `~/CODEBA/AnuncioNavio/ficha/`.
10. **Sem SMTP nesta fase**: "pedido de cadastro" vira linha em `data/pedidos.csv` + notificação.
11. **Cópia local antes de ler**: o robô copia a ficha para `tmp/`, lê a cópia e substitui o
    original atomicamente (`os.replace`); só processa com mtime estável ≥5 s e sem lock de
    LibreOffice (`.~lock.*#`). Se o arquivo mudar durante o processamento, aborta e tenta no ciclo
    seguinte. Duplicata (mesmo IMO+ETA em `status.json` já anunciado, item 19) é arquivada sem anunciar.
12. **Instância única** (lock `fcntl` em `logs/`, herdado pelo serviço) e **log rotativo**
    (30 dias) em `logs/`.
13. **Orquestração**: o serviço observa só `ficha/`; a conversão é a mesma que já existe
    (`planilha.construir_payload` + validações de `inserir.py`) e o anúncio chama as funções do
    `run.py` **no próprio processo** (sem subprocesso, sem depender de PATH). O JSON continua
    sendo gerado em `data/json/` como contrato/evidência de integração, mas quem anuncia é a
    biblioteca — `run.py --fila` segue funcionando para integradores externos.
14. **Senha em runtime**: `Config.from_env` lê `OPENPORT_SENHA` do ambiente e, se ausente, busca
    no Keychain (`security find-generic-password -s com.codeba.anuncionavio.openport -w`) — sem
    dependência nova. O `config/.env` guarda só URL, flags e login.
15. **`ANUNCIO_ROOT`** (nome já usado no código) é o resolvedor: no Mac o plist o aponta para
    `~/CODEBA/AnuncioNavio` e define `PLAYWRIGHT_BROWSERS_PATH`; sem a variável, a raiz é o repo
    (desenvolvimento/QAS continuam iguais, com `dados_rpa/`).
16. **Planilha aberta**: `lsof -t <ficha>` (qualquer processo com o arquivo aberto, Excel ou
    LibreOffice) + `mtime` estável ≥5 s + lock `.~lock.*#`; se aberta, espera e notifica uma vez.
    Save tardio de janela antiga é coberto pela anti-duplicidade.
17. **Ordem atômica**: cópia para `tmp/` → processa → grava o resultado num workbook temporário.
    **Sucesso:** arquiva o original preenchido em `arquivo/` (nome com DUV) e faz
    `os.replace(tmp_ficha_nova, ficha)`. **Falha:** `os.replace(tmp_com_resultado, ficha)` — a
    mesma ficha permanece, com o veredito. Nunca se edita o arquivo no lugar.
18. **`CONFIGURAR`**: mesmo fluxo para primeira vez e troca de senha; grava num item temporário
    do Keychain, testa o login (read-only) e só então promove (`-U`) e reinicia o serviço —
    senha errada não derruba a configuração boa.
19. **Duplicidade por conteúdo**: a viagem é reservada pelo robô, então uma ficha antiga re-salva
    ganharia viagem nova e anunciaria de novo. Regra: mesmo **IMO + mesma ETA (data e hora)** já
    presente em `status.json` = duplicado — arquiva sem anunciar e gera ficha nova.
20. **Ficha parada não é reprocessada**: `data/estado_ficha.json` guarda `mtime` e tamanho da
    última tentativa; ficha inalterada não roda de novo (nem repete notificação). Depois de
    escrever o veredito, o robô registra o novo `mtime`.
21. **`data/`** (não `dados/`): `status.py` e `sequencia.py` já resolvem `project_root/data/`;
    o layout mantém esse nome para não duplicar estado.

## 6. Layout em produção

```
~/CODEBA/AnuncioNavio/
  app/            código + runtime/ + browsers/ + recursos/ + VERSION   (trocado no update)
  config/         .env (não-secreto) + CONFIGURAR.command               (preservado no update)
  ficha/          ficha_anuncio_navio.xlsx  ← SEMPRE uma, em branco ou pendente
    arquivo/      fichas processadas (evidência)
  data/           status.json, sequencia.json, estado_ficha.json, historico.csv,
                  pedidos.csv, json/ (contrato)                                  (preservado)
  logs/           servico.log, anuncio_AAAA-MM-DD.log, servico.lock
  relatorios/     screenshots/  tmp/
```

`ANUNCIO_ROOT` (padrão: raiz do repo, para desenvolvimento/QAS) resolve os caminhos; no Mac vem do
plist. `dados_rpa/` e `entrada/` deixam de existir no deploy (o JSON continua aceito pelo
`run.py` para o contrato de integração).

## 7. O dia do agente

1. Duplo clique em "Anúncio de Navio" (Área de Trabalho) → abre a pasta com a ficha em branco.
2. Abre a ficha, preenche (nomes dos campos de cadastro; código também vale), confere a `C3`.
3. `Cmd+S` e **fecha** o app. (Se esquecer de fechar, a notificação lembra; nada se perde.)
4. Em ≤10 s o robô lê, resolve os lookups, abre o OpenPort em headless, grava, verifica e confirma.
5. Notificação: "Anúncio <IMO> viagem <X> gravado — DUV <Y>". A ficha preenchida vai para
   `ficha/arquivo/` com o veredito na `C3`; no lugar já está a próxima em branco, e a aba
   `HISTÓRICO` dela mostra a linha do anúncio concluído.

## 8. Fluxos de erro

| Situação | Robô | O agente vê |
|---|---|---|
| Campo faltando | não grava; `C3` com a lista | `C3` = "FALTAM 2 CAMPOS (IMO, CARGA)" |
| Nome não encontrado | não grava; `pedidos.csv` | `C3` = "PEDIDO: armador 'X' não cadastrado" |
| Ambíguo | não grava; `pedidos.csv` com candidatos | `C3` = "PEDIDO: 2 armadores com 'AMELIA'" |
| Senha mudou | não grava | `C3` = "a senha do OpenPort mudou — rode CONFIGURAR" |
| OpenPort fora / timeout | não grava; retenta no ciclo | `C3` = "OpenPort indisponível, tentando de novo" |
| Já anunciado (IMO+viagem) | arquiva sem anunciar | `C3` = "JÁ ANUNCIADO (DUV X)" |
| Planilha aberta | espera (3 ciclos) e notifica | notificação "feche a planilha para processar" |
| Serviço parado | — | `launchd` religa; se não, notificação "serviço parado" |

## 9. Instalação (`ATUALIZAR.command`, uma vez)

1. `uname -m` → escolhe `runtime-{arm64,x86_64}`; confere macOS ≥ 12 e espaço em disco.
2. Descompacta `app/` e `runtime/`; valida `app/VERSION` e o Chromium (`--version`).
3. `CONFIGURAR`: diálogos (login/senha) → Keychain + `config/.env` com URL PROD e flags.
4. Detecta Excel; se ausente, instala LibreOffice do pacote e cria o atalho AppleScript.
5. Cria pastas, copia `ficha_modelo.xlsx` → `ficha/`, cria o apelido na Área de Trabalho.
6. Escreve e carrega o LaunchAgent; verifica `launchctl print gui/$UID/com.codeba.anuncionavio`.
7. **Smoke test read-only**: login + abrir 2001/2003 com a credencial dele; nada é gravado.
   Falha → notificação com o motivo (rede/permissão/senha) e rollback do serviço (não sobe).
8. Notificação "instalado". O primeiro anúncio real é o primeiro navio dele.

## 10. Atualização (mesmo `ATUALIZAR.command`)

Baixa/leva o novo `app/` → para o serviço → troca `app/` (nunca `config/`, `data/`, `ficha/`) →
recarrega o LaunchAgent → notifica a versão. Se a nova versão falhar no smoke test, restaura o
`app/` anterior (guarda `app.anterior/`).

## 11. Riscos e perguntas em aberto

1. **Rede corporativa**: o Mac do agente alcança `openportilheus.codeba.gov.br` fora da CODEBA?
   (smoke test responde no dia da instalação.)
2. **Gatekeeper**: `.command` baixado exige clique direito → Abrir (ou `xattr -d
   com.apple.quarantine`); testar no Mac real antes de entregar.
3. **Tampa fechada/suspensão**: `caffeinate -s` só segura ocioso na tomada; com a tampa fechada o
   Mac dorme e o robô espera até reabrir. No dia da instalação decidimos entre `sudo pmset -a
   disablesleep 1` (segura com a tampa fechada, reversível com `disablesleep 0`; bateria/calor se
   ficar fora da tomada) ou só a instrução "deixe aberto e na tomada".
4. **Excel mantém o arquivo aberto**: `os.replace` funciona, mas um save tardio do Excel pode
   reintroduzir a ficha antiga; a anti-duplicidade a arquiva sem anunciar de novo.
5. **LibreOffice**: download/instalação no dia (tamanho ~350 MB) e associação de `.xlsx`.
6. Tempo de instalação estimado: 20–30 min no local (runtime + Chromium + teste).

## 12. Fora de escopo

Fases 4 e 5 da spec original (fila de pedidos com SMTP, auto-update, backup remoto, cadastro
automatizado CODEBA) e a correção manual de calados na desatracação (continua manual).
