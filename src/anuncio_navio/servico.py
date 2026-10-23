"""Um ciclo do servico da ficha unica.

Valida a ficha parada, anuncia pelo `main`, devolve o veredito na C3,
arquiva a ficha preenchida e deixa uma nova em branco. Tudo o que toca a
rede/browser passa por `executar`, que os testes substituem por um fake.
"""
from __future__ import annotations

import json
import logging
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

logger = logging.getLogger("anuncio.servico")

MSG_SENHA = "NÃO FOI ENVIADO — a senha do OpenPort mudou. Rode CONFIGURAR.command."
MSG_FALHA = "NÃO FOI ENVIADO — veja a ficha (linha STATUS)."


@dataclass(frozen=True)
class Resultado:
    estado: str
    mensagem: str = ""
    duv: str = ""


def _avisar(notificar_fn, titulo: str, texto: str) -> None:
    fn = notificar_fn or notificar.notificar
    try:
        fn(titulo, texto)
    except Exception as exc:
        logger.warning(f"Falha ao notificar: {exc}")


def _notificar_duplicado(notificar_fn, duv: str) -> None:
    if duv:
        texto = f"Este navio já foi anunciado (DUV {duv}). A ficha foi arquivada."
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
    # O loop so chama o ciclo quando a ficha mudou; a janela de 5 s do
    # `esta_livre` faria toda ficha recem-salva virar "ocupada". Lock/lsof
    # continuam barrando a planilha aberta.
    if not ficha.esta_livre(p, agora=agora, estavel_seg=0):
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
        imo = payload.get("imo", "")
        viagem = payload.get("viagem", "")
        ficha.arquivar(root, p, imo=imo, viagem=viagem, duv=dup)
        _registrar(root, payload, "JÁ ANUNCIADO", duv=dup, quando=agora)
        ficha.gerar_nova(root)
        ficha.marcar_estado(root, caminhos.ficha(root))
        _notificar_duplicado(notificar_fn, dup)
        return Resultado("duplicado", duv=dup)

    payload["viagem"] = sequencia.proxima(root)
    arquivo = caminhos.json_dir(root) / f"{payload.get('imo','')}_{payload['viagem']}.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    executar = executar or main.executar_um
    try:
        dados = fila_json.carregar_anuncio(arquivo)
        duv = executar(cfg, dados) or ""
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

    imo = payload.get("imo", "")
    viagem = payload["viagem"]
    if duv == "duplicado":
        ficha.arquivar(root, p, imo=imo, viagem=viagem, duv="")
        _registrar(root, payload, "JÁ ANUNCIADO", quando=agora)
        ficha.gerar_nova(root)
        ficha.marcar_estado(root, caminhos.ficha(root))
        _notificar_duplicado(notificar_fn, "")
        return Resultado(
            "duplicado",
            mensagem="Este navio já foi anunciado. A ficha foi arquivada.",
            duv="",
        )

    fila_json.finalizar_sucesso(arquivo, duv)
    _registrar(root, payload, "OK", duv=duv, quando=agora)
    ficha.arquivar(root, p, imo=imo, viagem=viagem, duv=duv)
    ficha.gerar_nova(root)
    ficha.marcar_estado(root, caminhos.ficha(root))
    _avisar(
        notificar_fn,
        "Anúncio",
        f"Anúncio {imo} viagem {viagem} gravado — DUV {duv}.",
    )
    return Resultado("ok", duv=duv)
