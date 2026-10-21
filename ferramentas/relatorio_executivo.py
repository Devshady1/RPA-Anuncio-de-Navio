# -*- coding: utf-8 -*-
"""Relatorio EXECUTIVO do primeiro anuncio em producao (linguagem de gestao)."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "relatorios" / "RELATORIO_EXECUTIVO_TI_SUNRISE_000006_20261013.pdf"
LOGO = ROOT / "logo_codeba_transp.png"
SHOT_FINAL = ROOT / "screenshots" / "anuncio_final_20261013_162127.png"
SHOT_2001 = ROOT / "screenshots" / "verificacao_2001_ok_20261013_162147.png"

NAVY = colors.HexColor("#0E2244")
GOLD = colors.HexColor("#C9A227")
LIGHT = colors.HexColor("#EEF1F6")
MID = colors.HexColor("#C9D2E0")
WHITE = colors.white

styles = getSampleStyleSheet()
s_title = ParagraphStyle("Titulo", parent=styles["Title"], fontSize=22, leading=26,
                         textColor=NAVY, spaceAfter=2 * mm, alignment=1)
s_sub = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=11, leading=14,
                       textColor=colors.HexColor("#33415C"), alignment=1, spaceAfter=6 * mm)
s_h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=13, leading=16,
                      textColor=WHITE, backColor=NAVY, borderPadding=(2 * mm, 2 * mm, 2 * mm),
                      spaceBefore=6 * mm, spaceAfter=3 * mm)
s_body = ParagraphStyle("Corpo", parent=styles["Normal"], fontSize=10, leading=14.5,
                        alignment=4, spaceAfter=2.5 * mm)
s_cell = ParagraphStyle("Cel", parent=styles["Normal"], fontSize=9, leading=12)
s_cell_b = ParagraphStyle("CelB", parent=s_cell, fontName="Helvetica-Bold")
s_cap = ParagraphStyle("Leg", parent=styles["Normal"], fontSize=8, leading=10,
                       textColor=colors.HexColor("#33415C"), alignment=1, spaceAfter=4 * mm)


def tab(dados, larguras):
    t = Table(dados, colWidths=larguras, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, MID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    return t


def P(txt, estilo=None):
    return Paragraph(txt, estilo or s_body)
C = lambda txt: Paragraph(txt, s_cell)  # noqa: E731
CB = lambda txt: Paragraph("<b>%s</b>" % txt, s_cell_b)  # noqa: E731
CH = lambda txt: Paragraph("<b><font color='white'>%s</font></b>" % txt, s_cell)  # noqa: E731


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#5A6B8C"))
    canvas.drawString(15 * mm, 12 * mm,
                      "CODEBA - Automação de anúncio de navios  |  TI SUNRISE - Viagem 000006")
    canvas.drawRightString(A4[0] - 15 * mm, 12 * mm, "Pág. %d" % doc.page)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.6)
    canvas.line(15 * mm, 14.5 * mm, A4[0] - 15 * mm, 14.5 * mm)
    canvas.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                        topMargin=15 * mm, bottomMargin=20 * mm,
                        title="Relatorio Executivo - Primeiro anuncio em producao",
                        author="Automação de anúncio de navios - CODEBA")
story = []

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

story.append(P("RELATÓRIO EXECUTIVO", s_title))
story.append(P("Primeiro anúncio de navio em <b>produção</b> executado pela automação "
               "de anúncios de navios (sistema OpenPort / CODEBA)", s_sub))

story.append(tab([
    [CH("Informação"), CH("Detalhe")],
    [CB("Navio"), C("TI SUNRISE (IMO 9701009)")],
    [CB("Viagem / anúncio nº"), C("000006 / DUV 000006")],
    [CB("Programação gerada"), C("1772")],
    [CB("Chegada prevista"), C("16/10/2026 às 11h00")],
    [CB("Rota"), C("Santa Cruz de Tenerife (Espanha) - Ilhéus - Tianjin (China)")],
    [CB("Carga"), C("Níquel - 11.200 toneladas")],
    [CB("Data da operação"), C("13/10/2026, das 16h20 às 16h22")],
    [CB("Resultado"), C("<b>Anúncio confirmado com sucesso</b> (status Anunciado)")],
], [50 * mm, 130 * mm]))

story.append(P("1. Objetivo", s_h1))
story.append(P("Demonstrar que a automação anuncia navios em produção com o mesmo rigor do "
               "processo assistido, deixando trilha de auditoria completa (telas capturadas e "
               "registro da operação) e liberando a equipe para as conferências de negócio."))

story.append(P("2. Resultado", s_h1))
story.append(P("Em 13/10/2026, o navio <b>TI SUNRISE</b> foi anunciado e <b>confirmado no sistema "
               "OpenPort em cerca de 3 minutos de operação acompanhada em tela</b>, com verificação "
               "independente do aceite: programação <b>1772</b>, chegada prevista 16/10/2026 e status "
               "<b>Anunciado</b>. Os dados da viagem haviam sido validados antes da execução "
               "(documento do navio, códigos de agência, armador, operador, portos e carga)."))

story.append(P("3. Como foi a operação", s_h1))
for item in [
    "<b>16h20</b> - Início da operação acompanhada em tela: acesso ao sistema, abertura do anúncio e preenchimento conferido campo a campo.",
    "<b>16h21</b> - Gravação, verificação automática de inconsistências e confirmação pelo próprio sistema (<i>Anúncio confirmado com sucesso</i>).",
    "<b>16h21</b> - Conferência independente na tela de programação: navio localizado com programação 1772 e status Anunciado.",
    "<b>16h22</b> - Arquivamento automático das evidências e encerramento sem pendências.",
]:
    story.append(P(item, s_body))

story.append(P("4. Evidências", s_h1))
if SHOT_FINAL.exists():
    story.append(Image(str(SHOT_FINAL), width=150 * mm, height=150 * mm * 0.55))
    story.append(P("Figura 1 - Anúncio confirmado na tela de cadastro do navio.", s_cap))
if SHOT_2001.exists():
    story.append(Image(str(SHOT_2001), width=150 * mm, height=150 * mm * 0.55))
    story.append(P("Figura 2 - Programação 1772 com status Anunciado na tela de consulta.", s_cap))

story.append(P("5. Pontos de atenção e próximos passos", s_h1))
for item in [
    "<b>Ajustes manuais previstos:</b> os calados de saída e as janelas de atracação/operação serão atualizados manualmente após a chegada do navio, conforme a prática operacional.",
    "<b>Recomendação:</b> reconferir os calados de chegada junto ao comandante antes dos ajustes definitivos.",
    "<b>Escala:</b> com a primeira operação em produção validada, a automação está apta a atender os próximos navios; a nova forma de entrada de dados e a integração à torre de automação são os próximos passos.",
]:
    story.append(P(item, s_body))

story.append(P("Documento gerado automaticamente a partir dos registros da operação de 13/10/2026.",
               ParagraphStyle("Fim", parent=s_body, alignment=1, textColor=colors.HexColor("#5A6B8C"))))

doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
print("PDF OK:", OUT, OUT.stat().st_size, "bytes")
