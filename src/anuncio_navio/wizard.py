"""Wizard terminal — sem planilha, sem e-mail. Entrada manual didatica."""
import json
import re
from pathlib import Path


def _ask(txt, obrig=True, default=""):
    while True:
        v = input(f"{txt}" + (f" [{default}]" if default else "") + ": ").strip() or default
        if v or not obrig:
            return v
        print("  Obrigatorio.")


def _ask_opcao(rotulo, opcoes: dict):
    print(f"\n{rotulo}:")
    for k in sorted(opcoes, key=lambda x: int(x)):
        print(f"  {k} = {opcoes[k]}")
    while True:
        v = input("Escolha o numero: ").strip()
        if v in opcoes:
            return v
        print("  Opcao invalida.")


def _ask_data(rotulo):
    while True:
        v = input(f"{rotulo} DD/MM/AAAA (ou vazio): ").strip()
        if not v:
            return ""
        if re.match(r"^\d{2}/\d{2}/\d{4}$", v):
            return v
        print("  Formato DD/MM/AAAA.")


def _ask_hora(rotulo):
    while True:
        v = input(f"{rotulo} HH:MM (ou vazio): ").strip()
        if not v:
            return ""
        if re.match(r"^\d{2}:\d{2}$", v):
            return v
        print("  Formato HH:MM.")


def coletar(config, colar_email="") -> dict:
    print("\n=== NOVO ANUNCIO 2003 (QAS) ===")
    if colar_email:
        print("(modo colar-email: use os valores do e-mail nas respostas abaixo)")
    d = {}
    d["imo"] = _ask("IMO / Num Capitania")
    d["viagem"] = _ask("Viagem (COD_VIAGEM)")
    d["tipo_viagem"] = _ask_opcao("Tipo de Viagem", config.opcoes["tipo_viagem"])
    d["tipo_operacao"] = _ask_opcao("Tipo de Operacao", config.opcoes["tipo_operacao"])
    d["sentido"] = _ask_opcao("Sentido", config.opcoes["sentido"])
    d["natureza"] = _ask_opcao("Natureza", config.opcoes["natureza"])
    for k, rot in (("eta", "ETA"), ("etb", "ETB"), ("etc", "ETC"), ("ets", "ETS")):
        d[f"{k}_data"] = _ask_data(rot)
        d[f"{k}_hora"] = _ask_hora(rot)
    d["porto_ant"] = _ask("Ultimo Porto (codigo)")
    d["porto_prox"] = _ask("Proximo Porto (codigo)")
    d["armador"] = _ask("Armador (codigo)")
    d["afretador"] = _ask("Afretador (codigo)", obrig=False)
    d["agencia"] = _ask("Agencia (codigo)")
    d["berco"] = _ask("Berco preferencia (codigo)", obrig=False)
    d["operador"] = _ask("Operador (codigo)")
    d["calado_cheg_proa"] = _ask("Calado chegada PROA", obrig=False)
    d["calado_cheg_popa"] = _ask("Calado chegada POPA", obrig=False)
    d["calado_sai_proa"] = _ask("Calado saida PROA", obrig=False)
    d["calado_sai_popa"] = _ask("Calado saida POPA", obrig=False)
    d["carga"] = _ask("Carga predominante (codigo)")
    d["qtd"] = _ask("Unidades (QTD_CARGA)", obrig=False)
    d["tons"] = _ask("Tons previstas", obrig=False)
    print(f"\nResumo: IMO {d['imo']} Viagem {d['viagem']} ETA {d['eta_data']} {d['eta_hora']}")
    ok = input("Confirma e executa no OpenPort? (S/n): ").strip().lower()
    if ok not in ("", "s", "sim", "y"):
        return {}
    # salva copia local em data/fila para auditoria
    fila = config.project_root / "data" / "fila"
    fila.mkdir(parents=True, exist_ok=True)
    (fila / f"{d['imo']}_{d['viagem']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d
