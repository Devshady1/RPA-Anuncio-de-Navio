import json
from pathlib import Path


def _path(config) -> Path:
    p = config.project_root / "data" / "status.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(json.dumps({"anuncios": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def chave(d: dict) -> str:
    return f"{d.get('imo','')}_{d.get('viagem','')}"


def ja_feito(config, d: dict) -> bool:
    p = _path(config)
    st = json.loads(p.read_text(encoding="utf-8"))
    return chave(d) in st.get("anuncios", {})


def _eta(d: dict) -> str:
    eta = (d.get("eta") or "").strip()
    if eta:
        return eta
    return f"{d.get('eta_data','')} {d.get('eta_hora','')}".strip()


def marcar_ok(config, d: dict, duv: str):
    p = _path(config)
    st = json.loads(p.read_text(encoding="utf-8"))
    st["anuncios"][chave(d)] = {
        "imo": d.get("imo"),
        "viagem": d.get("viagem"),
        "eta": _eta(d),
        "duv": duv,
    }
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def mesmo_anuncio(config, d: dict) -> str:
    """DUV ja registrado para o mesmo IMO + ETA; "" quando nao ha."""
    p = _path(config)
    st = json.loads(p.read_text(encoding="utf-8"))
    imo = d.get("imo")
    eta = _eta(d)
    if not imo or not eta:
        return ""
    for anuncio in st.get("anuncios", {}).values():
        if anuncio.get("imo") == imo and anuncio.get("eta") == eta:
            return anuncio.get("duv") or ""
    return ""


def resumo(config) -> str:
    p = _path(config)
    st = json.loads(p.read_text(encoding="utf-8"))
    n = len(st.get("anuncios", {}))
    if not n:
        return "Nenhum anuncio em status.json."
    linhas = [f"{k} DUV={v.get('duv')}" for k, v in st["anuncios"].items()]
    return f"{n} anuncio(s):\n" + "\n".join(linhas)
