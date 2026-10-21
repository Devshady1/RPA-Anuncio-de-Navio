# -*- coding: utf-8 -*-
"""Relatorio industrial do primeiro anuncio em producao (TI SUNRISE 000006)."""
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "relatorios" / "RELATORIO_PROD_TI_SUNRISE_000006_20261013.pdf"
LOGO = ROOT / "logo_codeba_transp.png"
SHOT_FINAL = ROOT / "screenshots" / "anuncio_final_20261013_162127.png"
SHOT_2001 = ROOT / "screenshots" / "verificacao_2001_ok_20261013_162147.png"

NAVY = colors.HexColor("#0E2244")
GOLD = colors.HexColor("#C9A227")
LIGHT = colors.HexColor("#EEF1F6")
MID = colors.HexColor("#C9D2E0")
WHITE = colors.white
BLACK = colors.black

styles = getSampleStyleSheet()
s_title = ParagraphStyle("Titulo", parent=styles["Title"], fontSize=22, leading=26,
                         textColor=NAVY, spaceAfter=2 * mm, alignment=1)
s_sub = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=11, leading=14,
                       textColor=colors.HexColor("#33415C"), alignment=1, spaceAfter=6 * mm)
s_h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=13, leading=16,
                      textColor=WHITE, backColor=NAVY, borderPadding=(2 * mm, 2 * mm, 2 * mm),
                      spaceBefore=6 * mm, spaceAfter=3 * mm)
s_h1_gold = ParagraphStyle("H1g", parent=s_h1, backColor=colors.HexColor("#3A2E0A"))
s_body = ParagraphStyle("Corpo", parent=styles["Normal"], fontSize=9.5, leading=13.5,
                        alignment=4, spaceAfter=2 * mm)
s_cell = ParagraphStyle("Cel", parent=styles["Normal"], fontSize=8.5, leading=11)
s_cell_b = ParagraphStyle("CelB", parent=s_cell, fontName="Helvetica-Bold")
s_cap = ParagraphStyle("Leg", parent=styles["Normal"], fontSize=8, leading=10,
                       textColor=colors.HexColor("#33415C"), alignment=1, spaceAfter=4 * mm)


def tab(dados, larguras, cabecalho=True):
    t = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    est = [
        ("GRID", (0, 0), (-1, -1), 0.4, MID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("ROWBACKGROUNDS", (0, 1 if cabecalho else 0), (-1, -1), [WHITE, LIGHT]),
    ]
    if cabecalho:
        est += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(est))
    return t


def P(txt, estilo=s_body):
    return Paragraph(txt, estilo)


C = lambda txt: Paragraph(txt, s_cell)
CB = lambda txt: Paragraph("<b>%s</b>" % txt, s_cell_b)
CH = lambda txt: Paragraph("<b><font color='white'>%s</font></b>" % txt, s_cell)


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#5A6B8C"))
    canvas.drawString(15 * mm, 12 * mm,
                      "RPA Anuncio de Navio - CODEBA OpenPort  |  TI SUNRISE 9701009_000006 (PRODUCAO)")
    canvas.drawRightString(A4[0] - 15 * mm, 12 * mm, "Pag. %d" % doc.page)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.6)
    canvas.line(15 * mm, 14.5 * mm, A4[0] - 15 * mm, 14.5 * mm)
    canvas.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                        topMargin=15 * mm, bottomMargin=20 * mm,
                        title="Relatorio - Primeiro anuncio em producao via RPA",
                        author="RPA Anuncio de Navio")
story = []

# ---- capa: faixa navy com logo branco (versao transp) ----
if LOGO.exists():
    _logo = Image(str(LOGO), width=60 * mm, height=60 * mm * 0.442)
    _faixa = Table([[_logo]], colWidths=[180 * mm])
    _faixa.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
    ]))
    story.append(_faixa)
story.append(Spacer(1, 8 * mm))
story.append(P("RELATÓRIO DE ANÚNCIO DE NAVIO", s_title))
story.append(P("Primeiro anúncio em <b>produção</b> executado pelo RPA Anúncio de Navio "
               "(OpenPort / CODEBA) - Tela 2003 com confirmação na 2001", s_sub))

story.append(tab([
    [CH("Campo"), CH("Valor")],
    [CB("Navio"), C("TI SUNRISE")],
    [CB("IMO"), C("9701009")],
    [CB("Viagem / DUV"), C("000006 / 000006")],
    [CB("Programação (2001)"), C("1772")],
    [CB("ETA"), C("16/10/2026 11:00")],
    [CB("Status final"), C("Anunciado - <b>Anúncio confirmado com sucesso.</b>")],
    [CB("Ambiente"), C("PRODUÇÃO - https://openportilheus.codeba.gov.br/openportcodeba/")],
    [CB("Execução"), C("13/10/2026, 16:20:00 às 16:22:48")],
    [CB("Resultado"), C("<b>1 ok, 0 erros (EXIT=0)</b> - JSON arquivado em processados com DUV000006")],
], [45 * mm, 135 * mm]))

# ---- 1 resumo ----
story.append(P("1. Resumo executivo", s_h1))
story.append(P("Em 13/10/2026 o RPA Anúncio de Navio realizou seu <b>primeiro anúncio em produção</b>: "
               "o navio <b>TI SUNRISE (IMO 9701009)</b> foi anunciado na tela 2003 do OpenPort e "
               "<b>confirmado com sucesso</b>, com aceite verificado de forma independente na tela 2001 "
               "(Programação <b>1772</b>, ETA 16/10/2026, Status Anunciado). A execução correu "
               "de ponta a ponta sem erro, com o arquivo arquivado em "
               "<i>processados</i> e o <i>status.json</i> atualizado. Este relatório consolida dados de "
               "entrada, linha do tempo, validações, evidências e ressalvas."))

# ---- 2 dados ----
story.append(P("2. Dados de entrada (JSON 9701009_000006.json)", s_h1))
story.append(P("Montado a partir do Ship Particulars do navio (PDF) e dos dados da viagem informados "
               "pelo agente marítimo. Carga e calados jamais são adivinhados pelo projeto."))
story.append(tab([
    [CH("Campo"), CH("Valor lançado"), CH("Origem")],
    [CB("nome_navio / imo / loa"), C("TI SUNRISE / 9701009 / 179,93"), C("PDF Ship Particulars")],
    [CB("agencia / operador / berco"), C("30010 / 30002 / 101"), C("Informados; códigos validados na base")],
    [CB("armador / afretador"), C("00000000000005 / 00000000000005"), C("TAMAR, recém-cadastrada em PROD; código informado")],
    [CB("porto_ant / porto_prox"), C("ESTCI / CNTSN"), C("Tenerife e Tianjin sem o sufixo de país (só assim resolvem)")],
    [CB("eta / etb / etc / ets"), C("16/10 11:00 / 19/10 08:00 / 19/10 12:00 / 19/10 19:00"),
     C("ETA informada; demais pela regra +3 dias, com ajuste manual previsto")],
    [CB("carga / qtd / tons"), C("26040000 / 11,200 / 11,200"), C("NÍQUEL confirmado (código de 8 dígitos)")],
    [CB("calados chegada"), C("10 / 4 m (proa/popa)"), C("Informados pelo usuário")],
    [CB("calados saída"), C("10 / 4 m (proa/popa)"), C("<b>Placeholder</b> - correção manual prevista após o anúncio")],
    [CB("tipo_viagem/operação/sentido/natureza"), C("1 / 1 / 1 / 1"),
     C("Confirmados: longo curso, mov. de carga, exportação, sólido")],
    [CB("viagem / tpb"), C("000006 / (vazio)"), C("Reservada via sequencia.proxima; TPB não exigido")],
], [52 * mm, 62 * mm, 66 * mm]))

# ---- 3 timeline ----
story.append(P("3. Linha do tempo operacional", s_h1))
story.append(tab([
    [CH("Hora"), CH("Evento")],
    [CB("16:20:00"), C("Execução em PRODUÇÃO (PERMITIR_PROD=1, CONFIRMAR_ANUNCIO=1). Login OK.")],
    [CB("16:20:22-16:21:00"), C("Todos os 8 lookups resolvem via TAB (portos, armador, afretador, agência, berço, operador, carga).")],
    [CB("16:21:13"), C("Gravado. DUV=000006.")],
    [CB("16:21:14"), C("Verificar: 'Inconsistências verificadas com sucesso.'")],
    [CB("16:21:23"), C("'Anúncio confirmado com sucesso.' Finalizado. Screenshot anuncio_final.")],
    [CB("16:21:47"), C("Verificação independente na 2001: Programação 1772, IMO 9701009, ETA 16/10/2026, Status Anunciado. Screenshot de evidência.")],
    [CB("16:22:48"), C("JSON movido para processados/__DUV000006.json. Fila concluída: 1 ok, 0 erros. EXIT=0.")],
], [24 * mm, 156 * mm]))

# ---- 4 travas ----
story.append(P("4. Validações e travas de segurança", s_h1))
for item in [
    "<b>Trava anti-PROD:</b> URL de produção só opera com PERMITIR_PROD=1, autorizado expressamente para esta execução.",
    "<b>Confirmação gated:</b> a finalização do anúncio exige CONFIRMAR_ANUNCIO=1.",
    "<b>Carga e calado nunca adivinhados:</b> carga exige código de 8 dígitos e calado respeita o máximo do navio (10,527 m).",
    "<b>Confirmação real, não presumida:</b> status.marcar_ok() só executa após confirmado_na_2001() retornar True com IMO/ETA/viagem conferidos na grade e no cabeçalho do cadastro.",
    "<b>Anti-duplicidade:</b> chave imo_viagem em status.json; a viagem 000006 foi utilizada sem conflito.",
    "<b>Evidências automáticas:</b> screenshots do anúncio final e da verificação 2001, logs com diálogos do sistema e relatório da rodada.",
]:
    story.append(P(item, s_body, ))

# ---- 5 evidencias ----
story.append(P("5. Evidências", s_h1))
story.append(tab([
    [CH("Artefato"), CH("Conteúdo")],
    [CB("logs/run_000006_prod2.log"), C("Log da execução (16:20 às 16:22, EXIT=0).")],
    [CB("relatorios/rodada_021"), C("16:20 (OK IMO=9701009 Viagem=000006 DUV=000006).")],
    [CB("dados_rpa/processados/9701009_000006__20261013_162248__DUV000006.json"), C("JSON final arquivado.")],
    [CB("screenshots"), C("anuncio_final_20261013_162127.png + verificacao_2001_ok_20261013_162147.png.")],
], [80 * mm, 100 * mm]))
if SHOT_FINAL.exists():
    story.append(Image(str(SHOT_FINAL), width=150 * mm, height=150 * mm * 0.55))
    story.append(P("Figura 1 - Tela 2003 após confirmação (anuncio_final_20261013_162127.png).", s_cap))
if SHOT_2001.exists():
    story.append(Image(str(SHOT_2001), width=150 * mm, height=150 * mm * 0.55))
    story.append(P("Figura 2 - Verificação na 2001: Programação 1772, Anunciado (verificacao_2001_ok_20261013_162147.png).", s_cap))

# ---- 6 ressalvas ----
story.append(P("6. Ressalvas e pendências pós-anúncio", s_h1_gold))
for item in [
    "<b>Calados de saída 10/4 são placeholder</b> (copiados da chegada para adequação posterior): correção manual prevista pelo responsável.",
    "<b>ETB/ETC/ETS em 19/10</b> seguem a regra +3 dias após a ETA, com ajuste manual previsto.",
    "<b>Recomendação:</b> reconferir os calados de chegada 10/4 na fonte (trim de 6 m é atípico; o padrão fica abaixo de 1-2 m).",
]:
    story.append(P(item, s_body))

# ---- 7 conclusao ----
story.append(P("7. Conclusão", s_h1))
story.append(P("O RPA Anúncio de Navio executou seu <b>primeiro anúncio em produção com êxito total</b>: "
               "TI SUNRISE anunciado, confirmado e verificado de forma independente (Programação 1772), "
               "com trilha completa de auditoria em logs, screenshots, relatório da rodada e arquivo "
               "processado. As ressalvas acima são correções manuais previstas e não invalidam o anúncio. "
               "Documento gerado automaticamente a partir dos artefatos da execução em 13/10/2026."))

doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
print("PDF OK:", OUT, OUT.stat().st_size, "bytes")
