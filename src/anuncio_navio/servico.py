"""Um ciclo do servico da ficha unica.

Valida a ficha parada, anuncia pelo `main`, devolve o veredito na C3,
arquiva a ficha preenchida e deixa uma nova em branco. Tudo o que toca a
rede/browser passa por `executar`, que os testes substituem por um fake.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from . import (
    caminhos,
    ficha,
    fila_json,
    historico,
    main,
    notificar,
    planilha,
    sequencia,
    status,
)
from .exceptions import LoginError, LookupError
from .resultado import ExecucaoAnuncio

logger = logging.getLogger("anuncio.servico")

MSG_SENHA = "NÃO FOI ENVIADO — a senha do OpenPort mudou. Rode CONFIGURAR.command."
MSG_FALHA = "NÃO FOI ENVIADO — veja a ficha (linha STATUS)."


@dataclass(frozen=True)
class Resultado:
    estado: str
    mensagem: str = ""
    duv: str = ""
    numero_requisicao: str = ""


def _avisar(notificar_fn, titulo: str, texto: str) -> None:
    fn = notificar_fn or notificar.notificar
    try:
        fn(titulo, texto)
    except Exception as exc:
        logger.warning(f"Falha ao notificar: {exc}")


def _notificar_duplicado(notificar_fn, duv: str, numero_requisicao: str = "") -> None:
    detalhes = []
    if numero_requisicao:
        detalhes.append(f"Requisição nº {numero_requisicao} (Programação)")
    if duv:
        detalhes.append(f"viagem/DUV {duv}")
    if detalhes:
        texto = f"Este navio já foi anunciado — {'; '.join(detalhes)}. A ficha foi arquivada."
    else:
        texto = "Este navio já foi anunciado. A ficha foi arquivada."
    _avisar(notificar_fn, "Anúncio", texto)


def _registrar(root: Path, d: dict, resultado: str, *, duv="", detalhe="", quando=None) -> None:
    historico.registrar(
        root,
        navio=d.get("nome_navio", ""),
        imo=d.get("imo", ""),
        viagem=d.get("viagem", ""),
        duv=duv,
        resultado=resultado,
        detalhe=detalhe,
        quando=quando,
    )


def _falhou(
    root: Path,
    p: Path,
    arquivo: Path,
    d: dict,
    erro: Exception,
    mensagem: str,
    notificar_fn,
    quando,
) -> Resultado:
    try:
        fila_json.finalizar_erro(arquivo, erro)
    except Exception as exc:
        logger.warning(f"Falha ao arquivar o JSON de erro: {exc}")
    ficha.escrever_status(p, mensagem)
    _registrar(root, d, "FALHOU", detalhe=mensagem, quando=quando)
    ficha.marcar_estado(root, p)
    _avisar(notificar_fn, "Anúncio", MSG_FALHA)
    return Resultado("falhou", mensagem=mensagem)


def processar(
    root: Path,
    cfg,
    *,
    executar=None,
    agora=None,
    notificar_fn=None,
) -> Resultado:
    root = Path(root)
    p = caminhos.ficha(root)
    if not p.exists():
        ficha.gerar_nova(root)
        return Resultado("sem_ficha")
    if ficha.ja_tentada(root, p):
        return Resultado("sem_novidade")
    # Respeita a janela de 5 s do `esta_livre`: ficha recem-salva ainda pode
    # estar sendo gravada. Lock/lsof continuam barrando a planilha aberta.
    if not ficha.esta_livre(p, agora=agora or time.time()):
        return Resultado("ocupada")

    campos, pendencias = ficha.ler(root)
    if pendencias:
        mensagem = ficha.mensagem_invalida(pendencias)
        ficha.escrever_status(p, mensagem)
        _registrar(root, campos, "FALHOU", detalhe=mensagem, quando=agora)
        ficha.marcar_estado(root, p)
        _avisar(notificar_fn, "Anúncio", MSG_FALHA)
        return Resultado("invalida", mensagem=mensagem)

    payload = planilha.construir_payload(campos)
    dup = status.mesmo_anuncio(cfg, payload)
    if dup:
        numero_requisicao = status.numero_requisicao_mesmo_anuncio(cfg, payload)
        imo = payload.get("imo", "")
        viagem = payload.get("viagem", "")
        ficha.arquivar(root, p, imo=imo, viagem=viagem, duv=dup)
        _registrar(
            root, payload, "JÁ ANUNCIADO", duv=dup,
            detalhe=f"REQUISICAO={numero_requisicao}" if numero_requisicao else "",
            quando=agora,
        )
        ficha.gerar_nova(root)
        ficha.marcar_estado(root, caminhos.ficha(root))
        _notificar_duplicado(notificar_fn, dup, numero_requisicao)
        return Resultado("duplicado", duv=dup, numero_requisicao=numero_requisicao)

    payload["viagem"] = sequencia.proxima(root)
    arquivo = caminhos.json_dir(root) / f"{payload.get('imo','')}_{payload['viagem']}.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    executar = executar or main.executar_um
    try:
        dados = fila_json.carregar_anuncio(arquivo)
        execucao = executar(cfg, dados)
    except LoginError as erro:
        return _falhou(root, p, arquivo, payload, erro, MSG_SENHA, notificar_fn, agora)
    except LookupError as erro:
        historico.pedido(root, tipo="PEDIDO", texto=str(erro), quando=agora)
        return _falhou(
            root, p, arquivo, payload, erro,
            f"NÃO FOI ENVIADO — {erro}", notificar_fn, agora,
        )
    except Exception as erro:
        primeira = str(erro).splitlines()[0] if str(erro) else type(erro).__name__
        return _falhou(
            root, p, arquivo, payload, erro,
            f"NÃO FOI ENVIADO — {primeira}. A ficha foi mantida; salve de novo para tentar.",
            notificar_fn, agora,
        )

    if isinstance(execucao, ExecucaoAnuncio):
        duv = execucao.duv
        numero_requisicao = execucao.numero_requisicao
    else:
        duv = execucao or ""
        numero_requisicao = ""

    imo = payload.get("imo", "")
    viagem = payload["viagem"]
    if duv == "duplicado":
        numero_requisicao = numero_requisicao or status.numero_requisicao_mesmo_anuncio(cfg, payload)
        ficha.arquivar(root, p, imo=imo, viagem=viagem, duv="")
        _registrar(
            root, payload, "JÁ ANUNCIADO",
            detalhe=f"REQUISICAO={numero_requisicao}" if numero_requisicao else "",
            quando=agora,
        )
        ficha.gerar_nova(root)
        ficha.marcar_estado(root, caminhos.ficha(root))
        _notificar_duplicado(notificar_fn, "", numero_requisicao)
        return Resultado(
            "duplicado",
            mensagem="Este navio já foi anunciado. A ficha foi arquivada.",
            duv="",
            numero_requisicao=numero_requisicao,
        )

    if not numero_requisicao:
        mensagem = (
            "RESULTADO PENDENTE DE CONFERÊNCIA — o OpenPort não devolveu o "
            "número da requisição/programação. O anúncio pode ter sido registrado; "
            "confirme a situação antes de tentar novamente."
        )
        ficha.escrever_status(p, mensagem)
        _registrar(root, payload, "SEM NÚMERO DA REQUISIÇÃO", duv=duv,
                   detalhe=mensagem, quando=agora)
        ficha.marcar_estado(root, p)
        _avisar(notificar_fn, "Anúncio pendente de conferência", mensagem)
        return Resultado("pendente", mensagem=mensagem, duv=duv)

    ficha.escrever_status(
        p,
        f"ANÚNCIO CONFIRMADO — Requisição nº {numero_requisicao} "
        f"(Programação). Viagem/DUV: {viagem}.",
    )
    fila_json.finalizar_sucesso(arquivo, duv)
    _registrar(
        root, payload, "OK", duv=duv,
        detalhe=f"REQUISICAO={numero_requisicao}", quando=agora,
    )
    ficha.arquivar(root, p, imo=imo, viagem=viagem, duv=duv)
    ficha.gerar_nova(root)
    ficha.marcar_estado(root, caminhos.ficha(root))
    _avisar(
        notificar_fn,
        "Anúncio",
        f"ANÚNCIO CONFIRMADO — Requisição nº {numero_requisicao} "
        f"(Programação). Navio {imo}; viagem/DUV {viagem}.",
    )
    return Resultado("ok", duv=duv, numero_requisicao=numero_requisicao)
