# -*- coding: utf-8 -*-
"""Gera o relatorio executivo redesenhado do anuncio TI SUNRISE em producao."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "relatorios" / "RELATORIO_PROD_TI_SUNRISE_000006_20261013_REVISADO.pdf"
LOGO = ROOT / "logo_codeba_transp.png"
SHOT_FINAL = ROOT / "screenshots" / "anuncio_final_20261013_162127.png"
SHOT_2001 = ROOT / "screenshots" / "verificacao_2001_ok_20261013_162147.png"

NAVY = colors.HexColor("#12304A")
BLUE = colors.HexColor("#1E5875")
GOLD = colors.HexColor("#C7A451")
INK = colors.HexColor("#243746")
MUTED = colors.HexColor("#617382")
PALE = colors.HexColor("#F2F6F8")
LINE = colors.HexColor("#D9E2E8")
GREEN = colors.HexColor("#19734A")
GREEN_PALE = colors.HexColor("#EAF5EF")
AMBER = colors.HexColor("#8A5A08")
AMBER_PALE = colors.HexColor("#FFF5E2")
WHITE = colors.white

REPORTLAB_FONTS = Path(__import__("reportlab").__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("ReportSans", str(REPORTLAB_FONTS / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ReportSans-Bold", str(REPORTLAB_FONTS / "VeraBd.ttf")))
REGULAR, BOLD = "ReportSans", "ReportSans-Bold"

styles = getSampleStyleSheet()
title = ParagraphStyle(
    "ReportTitle", parent=styles["Title"], fontName=BOLD, fontSize=25,
    leading=29, textColor=NAVY, alignment=TA_LEFT, spaceAfter=2 * mm,
)
subtitle = ParagraphStyle(
    "ReportSubtitle", parent=styles["Normal"], fontName=REGULAR, fontSize=10,
    leading=14, textColor=MUTED, alignment=TA_LEFT, spaceAfter=4 * mm,
)
section = ParagraphStyle(
    "Section", parent=styles["Heading2"], fontName=BOLD, fontSize=12,
    leading=15, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=3 * mm,
)
body = ParagraphStyle(
    "Body", parent=styles["BodyText"], fontName=REGULAR, fontSize=9.3,
    leading=13, textColor=INK, alignment=TA_LEFT, spaceAfter=2 * mm,
)
small = ParagraphStyle(
    "Small", parent=body, fontSize=8, leading=10.5, textColor=MUTED,
)
label = ParagraphStyle(
    "Label", parent=small, fontName=BOLD, fontSize=7.3,
    leading=9, textColor=MUTED, spaceAfter=1 * mm,
)
value = ParagraphStyle(
    "Value", parent=body, fontName=BOLD, fontSize=12,
    leading=15, textColor=NAVY, spaceAfter=0,
)
value_large = ParagraphStyle(
    "ValueLarge", parent=value, fontSize=16, leading=19,
)
white_small = ParagraphStyle(
    "WhiteSmall", parent=small, textColor=WHITE, alignment=TA_CENTER,
)
caption = ParagraphStyle(
    "Caption", parent=small, alignment=TA_CENTER, spaceBefore=1.5 * mm,
    spaceAfter=3 * mm,
)
timeline_time = ParagraphStyle(
    "TimelineTime", parent=small, fontName=BOLD, textColor=BLUE,
)


def P(text, style=body):
    return Paragraph(text, style)


def card(label_text, value_text, *, large=False, bg=PALE, accent=None):
    content = [
        P(label_text.upper(), label),
        P(value_text, value_large if large else value),
    ]
    table = Table([[content]], colWidths=[57 * mm])
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if accent:
        commands.append(("LINEBEFORE", (0, 0), (0, 0), 2, accent))
    table.setStyle(TableStyle(commands))
    return table


def section_title(text, eyebrow=None):
    flow = []
    if eyebrow:
        flow.append(P(eyebrow.upper(), label))
    flow.append(P(text, section))
    return flow


def data_table(rows, widths):
    prepared = [[P(a, label), P(b, body)] for a, b in rows]
    table = Table(prepared, colWidths=widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BACKGROUND", (0, 0), (0, -1), PALE),
    ]))
    return table


def timeline_table(rows):
    prepared = [
        [P(hora, timeline_time), P(evento, body)]
        for hora, evento in rows
    ]
    table = Table(prepared, colWidths=[35 * mm, 145 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.45, LINE),
        ("LINEBEFORE", (0, 0), (0, -1), 1.5, GOLD),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
    ]))
    return table


def callout(heading, text, *, bg=AMBER_PALE, accent=GOLD):
    content = [[
        P(f"<b>{heading}</b><br/>{text}", body)
    ]]
    table = Table(content, colWidths=[180 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, 0), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    return table


def draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(15 * mm, 15 * mm, A4[0] - 15 * mm, 15 * mm)
    canvas.setFont(REGULAR, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 10 * mm, "CODEBA  |  OPERAÇÃO TI SUNRISE  |  13 OUT 2026")
    canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"{doc.page}  /  3")
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(OUT),
    pagesize=A4,
    leftMargin=15 * mm,
    rightMargin=15 * mm,
    topMargin=13 * mm,
    bottomMargin=21 * mm,
    title="Relatório de operação - TI SUNRISE - anúncio em produção",
    author="RPA Anúncio de Navio - CODEBA",
    subject="Registro executivo e evidências do anúncio confirmado no OpenPort",
)
story = []

# Página 1: resultado e leitura executiva.
logo = Image(str(LOGO), width=42 * mm, height=42 * mm * 688 / 1555)
brand = Table(
    [[logo, P("OPERAÇÃO PORTUÁRIA<br/><b>RELATÓRIO DE ANÚNCIO</b>", white_small)]],
    colWidths=[52 * mm, 128 * mm],
    rowHeights=[22 * mm],
)
brand.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), NAVY),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
    ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
]))
story.extend([brand, Spacer(1, 7 * mm)])
story.append(P("TI SUNRISE", title))
story.append(P("Primeiro anúncio em produção • OpenPort / CODEBA • 13 de outubro de 2026", subtitle))

status = Table(
    [[P("<b>ANÚNCIO CONFIRMADO</b>", ParagraphStyle(
        "Confirmed", parent=body, fontName=BOLD, fontSize=12, leading=15,
        textColor=GREEN, spaceAfter=0,
    )), P("Validado na tela 2001<br/><b>Programação 1772 · Status Anunciado</b>", body)]],
    colWidths=[63 * mm, 117 * mm],
)
status.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), GREEN_PALE),
    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#B8D8C5")),
    ("LINEBEFORE", (0, 0), (0, 0), 3, GREEN),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
]))
story.append(status)
story.append(Spacer(1, 4 * mm))

metrics = Table([
    [card("IMO", "9701009", large=True), card("Viagem / DUV", "000006 / 000006", large=True),
     card("ETA", "16/10/2026 · 11h", large=True)],
    [card("Porto de destino", "Ilhéus"), card("Carga", "Níquel · 11.200 t"),
     card("Tempo de execução", "2 min 48 s")],
], colWidths=[60 * mm] * 3, hAlign="LEFT")
metrics.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
]))
story.append(metrics)
story.append(Spacer(1, 3 * mm))
story.extend(section_title("O que o resultado comprova"))
story.append(P(
    "O anúncio foi gravado e confirmado no OpenPort. Em seguida, o RPA fez uma "
    "conferência independente na consulta 2001, localizando o IMO, a ETA e a "
    "viagem no registro com status <b>Anunciado</b>. A operação terminou sem erro "
    "e o arquivo de entrada foi arquivado."
))

story.append(Spacer(1, 2 * mm))
story.extend(section_title("Etapas concluídas"))
steps = Table([[
    P("<b>16:20</b><br/>Acesso e preenchimento", small),
    P("<b>16:21</b><br/>Gravação e confirmação", small),
    P("<b>16:21</b><br/>Conferência na 2001", small),
    P("<b>16:22</b><br/>Arquivo e encerramento", small),
]], colWidths=[45 * mm] * 4)
steps.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), PALE),
    ("LINEBEFORE", (0, 0), (-1, -1), 1.2, GOLD),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
]))
story.append(steps)
story.append(Spacer(1, 4 * mm))
story.append(callout(
    "Ponto de atenção",
    "Os calados de saída foram preenchidos como estimativa e as datas ETB/ETC/ETS "
    "seguiram a regra operacional de +3 dias. A equipe deve conferir e ajustar "
    "esses dados conforme as informações finais do navio.",
))

# Página 2: dados e trilha operacional, com ressalvas explícitas.
story.append(PageBreak())
story.extend(section_title("Dados da viagem", "02 · Detalhamento"))
story.append(P(
    "Dados registrados no anúncio. Itens estimados ou sujeitos a ajuste estão identificados na coluna de origem.",
    small,
))
story.append(Spacer(1, 2 * mm))
story.append(data_table([
    ("Navio / IMO / LOA", "TI SUNRISE  ·  9701009  ·  179,93 m — dados do Ship Particulars"),
    ("Viagem / DUV / programação", "000006  ·  000006  ·  1772"),
    ("Rota", "Santa Cruz de Tenerife (Espanha) → Ilhéus → Tianjin (China)"),
    ("ETA", "16/10/2026 às 11:00 — informado para a operação"),
    ("ETB / ETC / ETS", "19/10/2026 às 08:00 / 12:00 / 19:00 — calculados pela regra +3 dias; ajuste previsto"),
    ("Agência / operador / berço", "30010 / 30002 / 101 — códigos informados e validados"),
    ("Armador / afretador", "00000000000005 / 00000000000005 — TAMAR, códigos informados"),
    ("Portos anterior / próximo", "ESTCI / CNTSN — Tenerife e Tianjin resolvidos sem sufixo de país"),
    ("Carga / quantidade", "Níquel · código 26040000 · 11.200 toneladas"),
    ("Calados de chegada", "10 m proa / 4 m popa — informado; recomenda-se reconferir a fonte"),
    ("Calados de saída", "10 m proa / 4 m popa — valor provisório; corrigir após confirmação operacional"),
    ("Classificação", "Longo curso · movimentação de carga · exportação · sólido"),
], [48 * mm, 132 * mm]))

story.append(Spacer(1, 5 * mm))
story.extend(section_title("Linha do tempo", "Execução acompanhada em tela"))
story.append(timeline_table([
    ("16:20:00", "Login concluído; início da operação em produção."),
    ("16:20–16:21", "Dados do navio e oito campos de cadastro preenchidos."),
    ("16:21:13", "Anúncio gravado com DUV 000006."),
    ("16:21:14", "Verificação de inconsistências concluída com sucesso."),
    ("16:21:23", "Confirmação aceita pelo OpenPort."),
    ("16:21:47", "Consulta independente na 2001: programação 1772, status Anunciado."),
    ("16:22:48", "Arquivo movido para processados; execução encerrada com 1 sucesso e 0 erros."),
]))
story.append(Spacer(1, 4 * mm))
story.append(callout(
    "Leitura responsável do resultado",
    "O anúncio foi confirmado e verificado. Isso não elimina a necessidade de "
    "atualizar os campos explicitamente provisórios antes das etapas operacionais "
    "seguintes. Os calados de chegada também merecem conferência com a fonte.",
))

# Página 3: evidências visuais e trilha de auditoria resumida.
story.append(PageBreak())
story.extend(section_title("Evidências da operação", "03 · Auditoria visual"))
story.append(P(
    "As imagens abaixo documentam o anúncio confirmado na tela 2003 e a conferência independente na tela 2001.",
    small,
))
story.append(Spacer(1, 2 * mm))
for path, description in (
    (SHOT_FINAL, "01  ·  Tela 2003 após a confirmação do anúncio"),
    (SHOT_2001, "02  ·  Tela 2001: programação 1772 com status Anunciado"),
):
    if path.exists():
        image = Image(str(path), width=174 * mm, height=174 * mm * 945 / 1920)
        image.hAlign = "CENTER"
        story.append(image)
        story.append(P(description, caption))

story.append(Spacer(1, 1 * mm))
story.extend(section_title("Referências de auditoria"))
story.append(data_table([
    ("Log da execução", "logs/run_000006_prod2.log"),
    ("Resumo da rodada", "relatorios/rodada_021 — OK · IMO 9701009 · viagem 000006 · DUV 000006"),
    ("Entrada processada", "dados_rpa/processados/9701009_000006__20261013_162248__DUV000006.json"),
], [48 * mm, 132 * mm]))
story.append(Spacer(1, 3 * mm))
doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
print(f"PDF OK: {OUT} ({OUT.stat().st_size:,} bytes)")
