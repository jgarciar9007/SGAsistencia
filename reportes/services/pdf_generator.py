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
from datetime import date, datetime, timedelta
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

    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%Y/%m/%d')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DE AUSENCIAS (DÍAS)", periodo, usuario)

    body_rows = [[r["nombre"], r["departamento"], r["tipo"], f'{r["ausencias"]}', f'{r["bajas"]}', r.get("observaciones", "")] for r in rows]
    table = _tabla_estilizada(
        headers=["Empleado / Usuario", "Departamento", "Tipo", "Ausencias", "Bajas", "Observaciones"],
        rows=body_rows,
        col_widths=[50 * mm, 40 * mm, 20 * mm, 15 * mm, 15 * mm, 40 * mm],
        style_overrides=[
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("ALIGN", (3, 1), (4, -1), "RIGHT"),
            ("ALIGN", (5, 1), (5, -1), "LEFT"),
            ("LEFTPADDING", (0, 1), (0, -1), 6),
            ("RIGHTPADDING", (3, 1), (4, -1), 6),
            ("LEFTPADDING", (5, 1), (5, -1), 6),
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

def build_pdf_rep_ausencias_empleado(request, d1: date, d2: date, meta: dict, rows: list, total_laborables: int) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    filename = f"reporte_ausencias_{meta.get('nombre','trabajador')}_{d1.strftime('%Y-%m')}.pdf"
    response["Content-Disposition"] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=20 * mm,
    )

    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')} (solo días laborables)"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DE AUSENCIAS POR TRABAJADOR", periodo, usuario)

    styles = getSampleStyleSheet()
    info_txt = (
        f"<b>Trabajador:</b> {meta.get('nombre','').upper()} &nbsp; "
        f"<b>Departamento:</b> {meta.get('departamento','')} &nbsp; "
        f"<b>Tipo:</b> {meta.get('tipo','')} &nbsp; "
        f"<b>Puesto:</b> {meta.get('puesto','')}"
    )
    story.append(Paragraph(info_txt, styles["Normal"]))
    story.append(Spacer(1, 4))

    total_ausencias = len(rows)
    resumen = f"Total días de ausencia: {total_ausencias} de {total_laborables} días laborables en el período."
    story.append(Paragraph(resumen, styles["Normal"]))
    story.append(Spacer(1, 8))

    # Tabla de días ausentes + fila TOTAL
    body_rows = []
    for r in rows:
        fecha_txt = r["fecha"].strftime("%d/%m/%Y")
        body_rows.append([fecha_txt, r["estado"], r.get("observaciones", "")])

    # Fila de totales al final
    body_rows.append(["TOTAL", f"{total_ausencias} días", ""])

    table = _tabla_estilizada(
        headers=["Fecha", "Estado", "Observaciones"],
        rows=body_rows,
        col_widths=[35 * mm, 50 * mm, 75 * mm],
        style_overrides=[
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("LEFTPADDING", (0, 1), (0, -1), 6),
        ]
    )

    n_rows = len(body_rows)
    last_idx = n_rows  # cabecera 0 + n_rows
    table.setStyle(TableStyle([
        ("FONTNAME", (0, last_idx), (1, last_idx), "Helvetica-Bold"),
        ("BACKGROUND", (0, last_idx), (1, last_idx), colors.HexColor("#F1F3F4")),
    ]))

    story.extend(
        [
            table,
            Spacer(1, 10),
            Paragraph("Consejo Nacional para el Desarrollo Económico y Social", styles["Normal"]),
        ]
    )

    doc.build(story)
    return response


def build_pdf_dashboard_listado(request, fecha, tipo: str, titulo: str, filas: list) -> HttpResponse:
    """PDF corporativo para las listas del dashboard (activos, firmaron, no firmaron, tarde)."""
    from datetime import date as date_type
    fecha_str = fecha.strftime("%d/%m/%Y") if isinstance(fecha, date_type) else str(fecha)
    tipo_safe = str(tipo)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="dashboard_{tipo_safe}_{fecha_str.replace("/", "-")}.pdf"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=20 * mm
    )

    periodo = f"FECHA: {fecha_str}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story(titulo.upper(), periodo, usuario)

    styles = getSampleStyleSheet()
    incluir_obs = (tipo_safe == "nofirmaron")

    if incluir_obs:
        estilo_obs = ParagraphStyle("Obs", parent=styles["Normal"], fontSize=8, leading=10)
        body_rows = [
            [
                r.get("nombre", ""),
                r.get("departamento", ""),
                r.get("tipo_vinculacion", ""),
                r.get("puesto", ""),
                r.get("detalle", ""),
                Paragraph(r.get("observaciones") or "No justificado", estilo_obs),
            ]
            for r in filas
        ]
        headers = ["Empleado", "Departamento", "Tipo", "Puesto", "Detalle", "Observaciones"]
        col_widths = [42 * mm, 35 * mm, 18 * mm, 28 * mm, 25 * mm, 42 * mm]
    else:
        body_rows = [
            [
                r.get("nombre", ""),
                r.get("departamento", ""),
                r.get("tipo_vinculacion", ""),
                r.get("puesto", ""),
                r.get("detalle", ""),
            ]
            for r in filas
        ]
        headers = ["Empleado", "Departamento", "Tipo", "Puesto", "Detalle"]
        col_widths = [55 * mm, 45 * mm, 22 * mm, 35 * mm, 33 * mm]

    if body_rows:
        table = _tabla_estilizada(
            headers=headers,
            rows=body_rows,
            col_widths=col_widths,
            style_overrides=[
                ("ALIGN", (0, 1), (0, -1), "LEFT"),
                ("LEFTPADDING", (0, 1), (0, -1), 6),
            ]
        )
        story.append(table)
    else:
        story.append(Paragraph("No hay registros para esta fecha.", styles["Normal"]))

    story.extend([
        Spacer(1, 10),
        Paragraph(f"Total: {len(filas)} registros", styles["Normal"]),
        Spacer(1, 6),
        Paragraph("Consejo Nacional para el Desarrollo Económico y Social", styles["Normal"]),
    ])

    doc.build(story)
    return response


def build_pdf_asistencia_general(request, d1: date, d2: date, rows: list, _hhmm_func) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="asistencia_general_{d1.strftime("%Y-%m")}.pdf"'

    from reportlab.lib.pagesizes import landscape, A4
    doc = SimpleDocTemplate(
        response, pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm
    )

    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DE ASISTENCIA GENERAL", periodo, usuario)

    body_rows = []
    for r in rows:
        body_rows.append([
            r["nombre"],
            r["departamento"],
            r["tipo"],
            r["fecha"].strftime("%d/%m/%Y"),
            r["entrada"].strftime("%H:%M") if r["entrada"] else "--:--",
            r["salida"].strftime("%H:%M") if r["salida"] else "--:--",
            _hhmm_func(r["total_horas"]) if r["total_horas"] else "--:--",
            r["estado"]
        ])

    table = _tabla_estilizada(
        headers=["Empleado", "Departamento", "Tipo", "Fecha", "Entrada", "Salida", "Horas", "Estado"],
        rows=body_rows,
        col_widths=[50*mm, 40*mm, 20*mm, 25*mm, 25*mm, 25*mm, 25*mm, 30*mm],
        style_overrides=[
            ("ALIGN", (0, 1), (1, -1), "LEFT"),
            ("ALIGN", (3, 1), (6, -1), "CENTER"),
            ("ALIGN", (7, 1), (7, -1), "LEFT"),
            ("LEFTPADDING", (0, 1), (0, -1), 4),
            ("RIGHTPADDING", (6, 1), (6, -1), 4),
        ]
    )

    story.extend([
        table, 
        Spacer(1, 10), 
        Paragraph("Consejo Nacional para el Desarrollo Económico y Social", getSampleStyleSheet()["Normal"])
    ])

    doc.build(story)
    return response


def build_pdf_ausencias_dia(request, d1: date, d2: date, rows: list) -> HttpResponse:
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="ausencias_por_dia_{d1.strftime("%Y-%m")}.pdf"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm, topMargin=25*mm, bottomMargin=20*mm
    )
    periodo = f"PERIODO: {d1.strftime('%d/%m/%Y')}  AL  {d2.strftime('%d/%m/%Y')}"
    usuario = f"GENERADO POR: {request.user.get_username().upper()}  |  FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story = _header_pdf_story("REPORTE DE AUSENCIAS POR DÍA", periodo, usuario)

    body_rows = []
    for r in rows:
        body_rows.append([
            r["fecha"].strftime("%d/%m/%Y"),
            r["nombre"],
            r["departamento"],
            r["tipo"],
            r["estado"],
            r.get("observaciones", "")
        ])

    table = _tabla_estilizada(
        headers=["Fecha", "Empleado", "Departamento", "Tipo", "Estado", "Observaciones"],
        rows=body_rows,
        col_widths=[30*mm, 50*mm, 40*mm, 20*mm, 25*mm, 35*mm],
        style_overrides=[
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
            ("ALIGN", (1, 1), (3, -1), "LEFT"),
            ("ALIGN", (4, 1), (4, -1), "CENTER"),
            ("ALIGN", (5, 1), (5, -1), "LEFT"),
            ("LEFTPADDING", (1, 1), (1, -1), 4),
            ("LEFTPADDING", (5, 1), (5, -1), 4),
        ]
    )
    story.extend([table, Spacer(1, 10), Paragraph("Consejo Nacional para el Desarrollo Económico y Social", getSampleStyleSheet()["Normal"])])

    doc.build(story)
    return response
