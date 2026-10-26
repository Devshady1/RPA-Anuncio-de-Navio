# RPA Anúncio de Navios — OpenPort/CODEBA

Automação em Python que preenche anúncios de navios no OpenPort da CODEBA e
verifica o resultado no próprio sistema. O projeto recebe os dados por planilha
ou JSON e utiliza o navegador para executar o fluxo de anúncio.

## Funcionalidades

- Leitura e validação da ficha de anúncio em Excel.
- Conversão das fichas em arquivos JSON para processamento em fila.
- Preenchimento do anúncio na tela 2003 e verificação na tela 2001.
- Consulta de cadastros pelo OpenPort, com tabelas locais como alternativa.
- Registro de status, histórico, logs e evidências da execução.
- Modo de serviço opcional para acompanhar uma ficha única.

## Requisitos

- Python 3.10 ou superior.
- Chromium instalado pelo Playwright.
- Credenciais de acesso ao OpenPort.

## Instalação

No PowerShell, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Configure `OPENPORT_LOGIN` e `OPENPORT_SENHA` no arquivo `.env`. Por padrão, o
projeto utiliza o ambiente de homologação (QAS). Mantenha as credenciais no
arquivo local `.env`; não as inclua no repositório.

## Entrada de dados

### Ficha Excel

O fluxo de várias fichas utiliza `ficha_anuncio_navio.xlsx`. Salve as fichas
preenchidas em `entrada/` e valide-as antes da conversão:

```powershell
python inserir.py entrada --simular
python inserir.py entrada
```

A conversão grava um JSON por anúncio em `dados_rpa/`. Fichas aceitas são
arquivadas em `entrada/processados/`; fichas rejeitadas vão para `entrada/erro/`
com o motivo da rejeição.

### Arquivo JSON

Também é possível fornecer anúncios diretamente como arquivos JSON na raiz de
`dados_rpa/`. Cada arquivo representa um anúncio e contém os dados do navio,
viagem, agência, portos, carga e horários. Datas e horas são informadas no
formato `DD/MM/AAAA HH:MM`. A fila considera apenas os arquivos diretamente
nessa pasta; subpastas são usadas para organizar os resultados.

## Execução

Consulte o status local:

```powershell
python run.py --status
```

Processe os JSONs pendentes ou um arquivo específico em QAS:

```powershell
python run.py --fila --ambiente qas
python run.py --json "dados_rpa\9553256_000004.json" --ambiente qas
```

O monitor acompanha as pastas `entrada/` e `dados_rpa/`, converte fichas e
aciona o processamento quando encontra anúncios pendentes:

```powershell
python monitor_fila.py --intervalo 10
```

Para utilizar o serviço de ficha única, preencha
`ficha/ficha_anuncio_navio.xlsx` e inicie:

```powershell
python monitor_fila.py --servico
```

Os comandos de processamento e monitoramento podem abrir o navegador e enviar
anúncios ao ambiente configurado. A execução em produção requer autorização
explícita por `PERMITIR_PROD=1`; a confirmação do anúncio também requer
`CONFIRMAR_ANUNCIO=1`. Use QAS para desenvolvimento e validações.

## Organização do projeto

| Caminho | Descrição |
| --- | --- |
| `src/anuncio_navio/` | Fluxo de automação, validação e integração com o OpenPort |
| `entrada/` | Fichas Excel aguardando conversão |
| `dados_rpa/` | Fila JSON e arquivos organizados por resultado |
| `tabelas/` | Dados locais de referência para cadastros |
| `data/` | Estado, sequência e histórico locais |
| `logs/`, `relatorios/`, `screenshots/` | Registros e evidências das execuções |
| `ficha/` | Ficha utilizada pelo modo de serviço opcional |
| `tests/` | Testes automatizados |

## Testes

```powershell
python -m unittest discover -s tests -v
```
