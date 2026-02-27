from typing import Sequence, List
from django.contrib.staticfiles import finders
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

def _header_pdf_story(titulo_mayus: str, periodo_txt: str, usuario_txt: str) -> List:
    """Crea encabezado común con logo centrado, título y subtítulos."""
    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "Titulo",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#333333"),
        spaceAfter=10,
        spaceBefore=4,
    )
    estilo_titulo.allCaps = True
    estilo_sub = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor("#555555"),
        leading=12,
    )

    story = []
    logo_path = finders.find("img/cndes-logo.png")
    if logo_path:
        img = RLImage(logo_path, width=50 * mm, height=25 * mm)
        img.hAlign = "CENTER"
        story.extend([img, Spacer(1, 4)])

    story.append(Paragraph(titulo_mayus, estilo_titulo))
    story.append(Paragraph(periodo_txt, estilo_sub))
    story.append(Paragraph(usuario_txt, estilo_sub))
    story.append(Spacer(1, 12))
    return story


def _tabla_estilizada(headers: Sequence[str], rows: Sequence[Sequence], col_widths: Sequence[float], style_overrides: list = None) -> Table:
    """Construye una tabla con encabezado corporativo y zebra rows."""
    data = [list(headers)] + [list(r) for r in rows]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Estilo base
    base_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18A052")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10),
        ("FONTSIZE",   (0, 1), (-1, -1), 9),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (0, 1), (-1, -1), "LEFT"), # [MODIFICADO] Default a la izquierda para el cuerpo
        ("ALIGN",      (0, 0), (-1, 0),  "CENTER"), # Cabecera centrada
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F8F9F9")]),
    ]
    
    if style_overrides:
        base_style.extend(style_overrides)
        
    table.setStyle(TableStyle(base_style))
    return table

from django.http import HttpResponse
from datetime import date, datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate

def build_pdf_nomina_horas(request, d1: date, d2: date, rows: list, _hhmm_func) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="reporte_horas_{d1.strftime("%Y-%m")}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=20 * mm)

    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DE HORAS TRABAJADAS", periodo, usuario)

    body_rows = [
        [r["nombre"], r["departamento"], r["tipo"], _hhmm_func(r["total"])]
        for r in rows
    ]
    table = _tabla_estilizada(
        headers=["Empleado / Usuario", "Departamento", "Tipo", "Horas Totales"],
        rows=body_rows,
        col_widths=[70 * mm, 65 * mm, 15 * mm, 20 * mm],
        style_overrides=[
            ("ALIGN", (0, 1), (0, -1), "LEFT"),   # Nombre a la izquierda
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),  # Horas a la derecha
            ("LEFTPADDING", (0, 1), (0, -1), 6),  # Padding extra textos
            ("RIGHTPADDING", (3, 1), (3, -1), 6), # Padding extra números
        ]
    )
    story.extend([table, Spacer(1, 10), Paragraph("Consejo Nacional para el Desarrollo Económico y Social", getSampleStyleSheet()["Normal"])])

    doc.build(story)
    return response

def build_pdf_ausencias_totales(request, d1: date, d2: date, rows: list) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="reporte_ausencias_{d1.strftime("%Y-%m")}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=20 * mm)

    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DE AUSENCIAS (DÍAS)", periodo, usuario)

    body_rows = [[r["nombre"], r["departamento"], r["tipo"], f'{r["ausencias"]}', f'{r["bajas"]}'] for r in rows]
    table = _tabla_estilizada(
        headers=["Empleado / Usuario", "Departamento", "Tipo", "Ausencias", "Bajas"],
        rows=body_rows,
        col_widths=[60 * mm, 50 * mm, 25 * mm, 20 * mm, 15 * mm],
        style_overrides=[
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("ALIGN", (3, 1), (4, -1), "RIGHT"),
            ("LEFTPADDING", (0, 1), (0, -1), 6),
            ("RIGHTPADDING", (3, 1), (4, -1), 6),
        ]
    )
    story.extend([table, Spacer(1, 10), Paragraph("Consejo Nacional para el Desarrollo Económico y Social", getSampleStyleSheet()["Normal"])])

    doc.build(story)
    return response

def build_pdf_solo_entrada(request, d1: date, d2: date, rows: list) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="reporte_solo_entrada_{d1.strftime("%Y-%m")}.pdf"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm, topMargin=25*mm, bottomMargin=20*mm
    )
    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DÍAS CON SOLO ENTRADA", periodo, usuario)

    body_rows = [[r["nombre"], r["departamento"], r["tipo"], f'{r["dias_solo_entrada"]}'] for r in rows]
    table = _tabla_estilizada(
        headers=["Empleado / Usuario", "Departamento", "Tipo", "Días con solo entrada"],
        rows=body_rows,
        col_widths=[70 * mm, 65 * mm, 15 * mm, 20 * mm],
        style_overrides=[
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("LEFTPADDING", (0, 1), (0, -1), 6),
            ("RIGHTPADDING", (3, 1), (3, -1), 6),
        ]
    )
    story.extend([table, Spacer(1, 10), Paragraph("Consejo Nacional para el Desarrollo Económico y Social", getSampleStyleSheet()["Normal"])])

    doc.build(story)
    return response

def build_pdf_reporte_empleado(request, d1: date, d2: date, meta: dict, rows: list, _hhmm_func) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    filename = f"reporte_{meta.get('nombre','usuario')}_{d1.strftime('%Y-%m')}.pdf"
    response["Content-Disposition"] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm, topMargin=25*mm, bottomMargin=20*mm
    )

    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DE ASISTENCIA POR TRABAJADOR", periodo, usuario)

    # Info trabajador
    styles = getSampleStyleSheet()
    info_txt = (
        f"<b>Trabajador:</b> {meta.get('nombre','').upper()} &nbsp; "
        f"<b>Departamento:</b> {meta.get('departamento','')} &nbsp; "
        f"<b>Tipo:</b> {meta.get('tipo','')} &nbsp; "
        f"<b>Puesto:</b> {meta.get('puesto','')}"
    )
    story.append(Paragraph(info_txt, styles["Normal"]))
    story.append(Spacer(1, 10))

    # Tabla
    body_rows = []
    total_segundos = 0
    for r in rows:
        fecha_txt = r["fecha"].strftime("%d/%m/%Y")
        ent_txt = r["entrada"].strftime("%H:%M") if r["entrada"] else "--:--"
        sal_txt = r["salida"].strftime("%H:%M") if r["salida"] else "--:--"
        tot_txt = _hhmm_func(r["total"])
        total_segundos += r["total"].total_seconds()
        body_rows.append([fecha_txt, ent_txt, sal_txt, tot_txt])

    # Fila de totales
    td_total = timedelta(seconds=total_segundos)
    body_rows.append(["TOTAL", "", "", _hhmm_func(td_total)])

    table = _tabla_estilizada(
        headers=["Fecha", "Entrada", "Salida", "Horas Trabajadas"],
        rows=body_rows,
        col_widths=[40 * mm, 35 * mm, 35 * mm, 40 * mm],
        style_overrides=[
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"), # Entradas, salidas y horas centradas
            ("LEFTPADDING", (0, 1), (0, -1), 6),
        ]
    )
    
    # Destacar fila TOTAL
    n_rows = len(body_rows)
    last_idx = n_rows  # 0 es cabecera, así que max iter es len(body_rows)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, last_idx), (-1, last_idx), "Helvetica-Bold"),
        ("BACKGROUND", (0, last_idx), (-1, last_idx), colors.HexColor("#F1F3F4")),
    ]))

    story.extend([table, Spacer(1, 10), Paragraph("Consejo Nacional para el Desarrollo Económico y Social", styles["Normal"])])

    doc.build(story)
    return response

def build_pdf_nomina_calculo(request, d1: date, d2: date, rows: list) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="descuentos_nomina_{d1.strftime("%Y-%m")}.pdf"'

    # Landscape A4 for more columns
    from reportlab.lib.pagesizes import landscape, A4
    doc = SimpleDocTemplate(
        response, pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm
    )

    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE PARA DESCUENTOS DE NÓMINA", periodo, usuario)

    def _fmt_moneda(val):
        return f"{val:,.0f}".replace(",", ".")

    body_rows = []
    total_descuentos = 0
    total_netos = 0
    total_aus = 0
    total_bajas = 0
    
    for r in rows:
        body_rows.append([
            r["nombre"],
            r["departamento"],
            _fmt_moneda(r["salario_base"]),
            str(r["ausencias"]),
            str(r["bajas"]),
            _fmt_moneda(r["descuento"]),
            _fmt_moneda(r["neto"]),
        ])
        total_descuentos += r["descuento"]
        total_netos += r["neto"]
        total_aus += r["ausencias"]
        total_bajas += r["bajas"]

    # Fila total general
    body_rows.append([
        "TOTAL GENERAL", "", "", 
        str(total_aus), str(total_bajas), 
        _fmt_moneda(total_descuentos), _fmt_moneda(total_netos)
    ])

    table = _tabla_estilizada(
        headers=["Empleado", "Departamento", "Salario Base", "Ausencias", "B. Aut.", "Descuento", "S. Neto Estimado"],
        rows=body_rows,
        col_widths=[75*mm, 50*mm, 30*mm, 20*mm, 20*mm, 30*mm, 35*mm],
        style_overrides=[
            ("ALIGN", (0, 1), (1, -1), "LEFT"),   # Nombre y Depto
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"), # Números a la derecha
            ("LEFTPADDING", (0, 1), (1, -1), 4),
            ("RIGHTPADDING", (2, 1), (-1, -1), 4),
        ]
    )

    # Destacar fila de TOTAL GENERAL
    n_rows = len(body_rows)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, n_rows), (-1, n_rows), "Helvetica-Bold"),
        ("BACKGROUND", (0, n_rows), (-1, n_rows), colors.HexColor("#F1F3F4")),
    ]))

    story.extend([
        table, 
        Spacer(1, 10), 
        Paragraph("Consejo Nacional para el Desarrollo Económico y Social", getSampleStyleSheet()["Normal"])
    ])

    doc.build(story)
    return response
