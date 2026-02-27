# reportes/views.py  — versión optimizada

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Sequence, Tuple

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.staticfiles import finders
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, Min, Max, OuterRef, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.timezone import make_aware
from django.views import View

from dispositivos.models import AsistenciaCruda, UsuarioDispositivo
from empleados.models import Empleado, BajaAutorizada


# ======================================================================================
# Utilidades comunes
# Configuración
from .services.pdf_generator import (
    _header_pdf_story, _tabla_estilizada, 
    build_pdf_nomina_horas, build_pdf_ausencias_totales, build_pdf_solo_entrada,
    build_pdf_reporte_empleado, build_pdf_nomina_calculo
)



def _parse_date_yyyy_mm_dd(s: str | None) -> date | None:
    """Parsea 'YYYY-MM-DD' a date. Devuelve None si vacío o inválido."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _range_default_mes_actual() -> Tuple[date, date]:
    """Primer y último día del mes local actual."""
    hoy = timezone.localdate()
    inicio = hoy.replace(day=1)
    next_month = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
    fin = next_month - timedelta(days=1)
    return inicio, fin


def _parse_rango_request(request, ini_key: str, fin_key: str) -> Tuple[date, date]:
    """Lee dos fechas del request. Si faltan, devuelve el mes actual."""
    d1 = _parse_date_yyyy_mm_dd(request.GET.get(ini_key))
    d2 = _parse_date_yyyy_mm_dd(request.GET.get(fin_key))
    if not d1 or not d2:
        return _range_default_mes_actual()
    return d1, d2


def _hhmm(td: timedelta | None) -> str:
    if not td:
        return "00:00"
    mins = int(td.total_seconds() // 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _laborables(d1: date, d2: date) -> Tuple[List[date], set]:
    """Devuelve lista y set de días laborables [L–V] en el rango."""
    cur, out = d1, []
    while cur <= d2:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out, set(out)


def _mapa_ud_para_pares(pares: Iterable[Tuple[int, str]]) -> Dict[Tuple[int, str], dict]:
    """
    Construye un mapa {(dispositivo_id, user_id) -> info UD + posible Empleado}.
    Optimiza: consulta única filtrada por dispositivos involucrados.
    """
    pares_set = set(pares)
    if not pares_set:
        return {}

    dispositivos_ids = {did for did, _ in pares_set}
    uds = (
        UsuarioDispositivo.objects
        .filter(dispositivo_id__in=dispositivos_ids, empleado__isnull=False)
        .select_related("empleado")
        .only(
            "dispositivo_id", "user_id", "nombre", "empleado_id",
            "empleado__nombre", "empleado__apellido",
            "empleado__departamento", "empleado__tipo_vinculacion", "empleado__puesto",
        )
    )

    mapa = {}
    for ud in uds:
        key = (ud.dispositivo_id, ud.user_id)
        if key in pares_set:
            mapa[key] = {
                "empleado_id": ud.empleado_id,
                "emp_nombre": getattr(ud.empleado, "nombre", None),
                "emp_apellido": getattr(ud.empleado, "apellido", None),
                "depto": getattr(ud.empleado, "departamento", "") or "",
                "tipo": getattr(ud.empleado, "tipo_vinculacion", "") or "",
                "puesto": getattr(ud.empleado, "puesto", "") or "",
                "ud_nombre": ud.nombre or "",
            }
    return mapa




def _filter_and_sort_rows(rows: List[dict], q: str = "", depto: str = "", sort: str = "nombre", order: str = "asc") -> List[dict]:
    """
    Utilidad para filtrar y ordenar las filas de los reportes antes de mostrar/exportar.
    """
    if q:
        q = q.lower()
        rows = [r for r in rows if q in (r.get("nombre") or "").lower()]
    
    if depto:
        rows = [r for r in rows if (r.get("departamento") or "") == depto]
    
    reverse = (order == "desc")
    
    def _get_sort_key(r):
        if sort == "nombre":
            return (r.get("nombre") or "").lower()
        if sort == "departamento":
            return (r.get("departamento") or "").lower()
        if sort == "horas" or sort == "total":
            val = r.get("total")
            return val if isinstance(val, timedelta) else timedelta(0)
        if sort == "ausencias":
            return r.get("ausencias") or 0
        if sort == "bajas":
            return r.get("bajas") or 0
        if sort == "solo_entrada":
            return r.get("dias_solo_entrada") or 0
        return (r.get("nombre") or "").lower()

    rows.sort(key=_get_sort_key, reverse=reverse)
    return rows


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# ======================================================================================
# Reporte: Asistencia general por día
# ======================================================================================

class ReporteAsistenciaGeneralView(View):
    template_name = "reportes/asistencia_general.html"
    page_size = 30

    @staticmethod
    def _parse_fecha(s: str | None, end: bool = False) -> datetime | None:
        if not s:
            return None
        try:
            d = datetime.strptime(s, "%Y-%m-%d")
            if end:
                d = d + timedelta(days=1) - timedelta(seconds=1)
            return d
        except Exception:
            return None

    def get(self, request):
        desde_raw = (request.GET.get("desde") or "").strip()
        hasta_raw = (request.GET.get("hasta") or "").strip()
        q = (request.GET.get("q") or "").strip()
        empleado_id = (request.GET.get("empleado") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()

        hoy = timezone.localdate()
        if not desde_raw and not hasta_raw:
            desde_raw = hoy.strftime("%Y-%m-%d")
            hasta_raw = hoy.strftime("%Y-%m-%d")

        desde = self._parse_fecha(desde_raw)
        hasta = self._parse_fecha(hasta_raw, end=True)

        # Base en rango
        base = AsistenciaCruda.objects.all()
        if desde:
            base = base.filter(ts__gte=desde)
        if hasta:
            base = base.filter(ts__lte=hasta)

        if q:
            base = base.filter(
                Q(usuario__empleado__nombre__icontains=q)
                | Q(usuario__empleado__apellido__icontains=q)
                | Q(usuario__empleado__numero__icontains=q)
                | Q(usuario__empleado__doc_id__icontains=q)
                | Q(usuario__nombre__icontains=q)
                | Q(user_id__icontains=q)
            )

        # Filtro por empleado: cubre registros con y sin FK usuario
        if empleado_id.isdigit():
            emp_id = int(empleado_id)
            ud_exists = UsuarioDispositivo.objects.filter(
                empleado_id=emp_id,
                dispositivo_id=OuterRef("dispositivo_id"),
                user_id=OuterRef("user_id"),
            )
            base = base.filter(Q(usuario__empleado_id=emp_id) | Exists(ud_exists))

        if depto:
            base = base.filter(usuario__empleado__departamento=depto)

        # Pares presentes
        pares = list(base.values_list("dispositivo_id", "user_id").distinct())
        mapa = _mapa_ud_para_pares(pares)

        # Agregado por día + identidad
        agg = (
            base.annotate(fecha=TruncDate("ts"))
            .values(
                "fecha", "dispositivo_id", "user_id",
                "usuario__nombre",  # podría ser None
                "usuario__empleado_id",
                "usuario__empleado__nombre",
                "usuario__empleado__apellido",
                "usuario__empleado__departamento",
            )
            .annotate(entrada=Min("ts"), salida=Max("ts"), n=Count("id"))
            .order_by("usuario__empleado__nombre", "usuario__empleado__apellido", "fecha", "user_id")
        )

        filas = []
        for r in agg:
            entrada = r["entrada"]
            if entrada:
                entrada = timezone.localtime(entrada)

            salida = r["salida"] if r["n"] >= 2 else None
            if salida:
                salida = timezone.localtime(salida)

            horas = (salida - entrada) if (entrada and salida and salida >= entrada) else timedelta(0)

            emp_id = r["usuario__empleado_id"]
            depto = ""
            if emp_id:
                # [MODIFICADO] Solo usamos datos de Empleado
                nombre = f"{r.get('usuario__empleado__nombre') or ''} {r.get('usuario__empleado__apellido') or ''}".strip()
                depto = r.get("usuario__empleado__departamento") or ""
            else:
                # [MODIFICADO] Buscar en mapa pero verificar que tenga empleado_id
                key = (r["dispositivo_id"], r["user_id"])
                info = mapa.get(key)
                if info and info.get("empleado_id"):
                    emp_id = info["empleado_id"]
                    nombre = f"{info.get('emp_nombre') or ''} {info.get('emp_apellido') or ''}".strip()
                    depto = info.get("depto") or ""
                else:
                    # [MODIFICADO] Sin empleado asociado -> no mostrar en reporte
                    continue

            filas.append({
                "fecha": r["fecha"],
                "empleado_id": emp_id,
                "nombre": nombre,
                "departamento": depto,
                "entrada": entrada,
                "salida": salida,
                "total_horas": _hhmm(horas),
            })

        paginator = Paginator(filas, self.page_size)
        page_obj = paginator.get_page(request.GET.get("page"))

        empleados = (
            Empleado.objects.filter(activo=True)
            .order_by("apellido", "nombre")
            .values("id", "nombre", "apellido")
        )

        ctx = {
            "desde": desde_raw,
            "hasta": hasta_raw,
            "q": q,
            "empleado": int(empleado_id) if empleado_id.isdigit() else "",
            "page_obj": page_obj,
            "total": len(filas),
            "empleados": empleados,
            "departamentos": sorted([d for d in Empleado.objects.values_list("departamento", flat=True).distinct() if d]),
            "depto_sel": depto,
        }
        return render(request, self.template_name, ctx)


# ======================================================================================
# Dashboard
# ======================================================================================

HORA_INICIO = 9  # 09:00
TOL_MINUTOS = 5  # tolerancia

def dashboard(request):
    """
    KPIs del panel usando USUARIOS DE DISPOSITIVO como universo activo.
    - empleados_total: total de UsuarioDispositivo activos con dispositivo activo.
    - firmaron_hoy: pares (dispositivo,user_id) con al menos un marcaje ese día.
    - no_firmaron_hoy = activos - firmaron_hoy.
    - llegadas_tarde: de los que firmaron, primer marcaje > 09:05.
    - gráfico mensual: firmantes por día en el mes de la fecha seleccionada.
    """
    # Fecha seleccionada
    fecha_str = (request.GET.get("fecha") or "").strip()
    fecha = _parse_date_yyyy_mm_dd(fecha_str) or timezone.localdate()

    # Rango día aware
    inicio_dia = make_aware(datetime(fecha.year, fecha.month, fecha.day, 0, 0, 0))
    fin_dia = make_aware(datetime(fecha.year, fecha.month, fecha.day, 23, 59, 59))

    # Universo activo: SOLO con empleado asignado
    set_activos = set(
        UsuarioDispositivo.objects
        .filter(activo=True, dispositivo__activo=True, empleado__isnull=False)
        .values_list("dispositivo_id", "user_id")
    )
    empleados_total = len(set_activos)

    # Marcajes del día
    firmas_dia: Dict[Tuple[int, str], datetime] = {}
    for did, uid, ts in AsistenciaCruda.objects.filter(ts__range=(inicio_dia, fin_dia)).values_list("dispositivo_id", "user_id", "ts"):
        key = (did, uid)
        if key in set_activos and (key not in firmas_dia or ts < firmas_dia[key]):
            firmas_dia[key] = ts

    firmaron_hoy = len(firmas_dia)
    no_firmaron_hoy = max(empleados_total - firmaron_hoy, 0)

    # Llegadas tarde
    limite = make_aware(datetime(fecha.year, fecha.month, fecha.day, HORA_INICIO, TOL_MINUTOS, 0))
    llegadas_tarde = sum(1 for ts in firmas_dia.values() if ts > limite)

    # Gráfico mensual
    _, last_day = monthrange(fecha.year, fecha.month)
    dias_labels = [str(d) for d in range(1, last_day + 1)]
    vistos_por_dia: List[set] = [set() for _ in range(last_day)]

    mes_ini = make_aware(datetime(fecha.year, fecha.month, 1, 0, 0, 0))
    mes_fin = make_aware(datetime(fecha.year, fecha.month, last_day, 23, 59, 59))

    for did, uid, ts in AsistenciaCruda.objects.filter(ts__range=(mes_ini, mes_fin)).values_list("dispositivo_id", "user_id", "ts"):
        key = (did, uid)
        if key in set_activos:
            vistos_por_dia[ts.day - 1].add(key)

    totales_por_dia = [len(s) for s in vistos_por_dia]

    ctx = {
        "fecha": fecha.strftime("%Y-%m-%d"),
        "empleados_total": empleados_total,
        "firmaron_hoy": firmaron_hoy,
        "no_firmaron_hoy": no_firmaron_hoy,
        "llegadas_tarde": llegadas_tarde,
        "dias": dias_labels,
        "totales": totales_por_dia,
    }
    return render(request, "reportes/dashboard.html", ctx)





# ya tienes estos dos arriba, los reutilizamos:
# HORA_INICIO = 9
# TOL_MINUTOS = 5

class DashboardListView(LoginRequiredMixin, StaffOnlyMixin, View):
    """
    Lista de personas para cada tarjeta del dashboard:
    tipo = activos | firmaron | nofirmaron | tarde
    """

    template_name = "reportes/dashboard_listado.html"

    def _parse_fecha(self, request) -> date:
        raw = (request.GET.get("fecha") or "").strip()
        if raw:
            try:
                return datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                pass
        return timezone.localdate()

    def _compute_sets(self, fecha: date):
        tz = timezone.get_current_timezone()
        inicio = make_aware(datetime(fecha.year, fecha.month, fecha.day, 0, 0, 0), tz)
        fin    = make_aware(datetime(fecha.year, fecha.month, fecha.day, 23, 59, 59), tz)

        # Universo: usuarios de dispositivo activos en dispositivos activos CON empleado
        uds_qs = (
            UsuarioDispositivo.objects
            .filter(activo=True, dispositivo__activo=True, empleado__isnull=False)
            .select_related("empleado")
            .only(
                "dispositivo_id",
                "user_id",
                "nombre",
                "empleado_id",
                "empleado__nombre",
                "empleado__apellido",
                "empleado__departamento",
                "empleado__tipo_vinculacion",
                "empleado__puesto",
            )
        )

        activos_pairs = [(u.dispositivo_id, u.user_id) for u in uds_qs]
        set_activos = set(activos_pairs)

        # Mapa de info por par (did, user_id)
        info_map = {}
        for u in uds_qs:
            key = (u.dispositivo_id, u.user_id)
            if u.empleado_id:
                nombre = f"{u.empleado.nombre} {u.empleado.apellido}".strip()
                departamento = u.empleado.departamento or ""
                tipo_v = u.empleado.tipo_vinculacion or ""
                puesto = u.empleado.puesto or ""
            else:
                nombre = (u.nombre or f"Usuario {u.user_id}").strip()
                departamento = tipo_v = puesto = ""
            info_map[key] = {
                "nombre": nombre or "(sin nombre)",
                "departamento": departamento,
                "tipo_vinculacion": tipo_v,
                "puesto": puesto,
            }

        # Marcajes del día
        base_dia = (
            AsistenciaCruda.objects
            .filter(ts__range=(inicio, fin))
            .values_list("dispositivo_id", "user_id", "ts")
        )

        # Primer marcaje por persona
        firmas = {}
        for did, uid, ts in base_dia:
            key = (did, uid)
            if key not in set_activos:
                continue
            if key not in firmas or ts < firmas[key]:
                firmas[key] = ts

        limite = make_aware(
            datetime(fecha.year, fecha.month, fecha.day, HORA_INICIO, TOL_MINUTOS, 0), tz
        )

        set_firmaron = set(firmas.keys())
        set_tarde = {k for k, ts in firmas.items() if ts > limite}
        set_nofirma = set_activos - set_firmaron

        return {
            "activos": set_activos,
            "firmaron": set_firmaron,
            "nofirmaron": set_nofirma,
            "tarde": set_tarde,
            "info": info_map,
            "firmas": firmas,
        }

    def get(self, request, tipo):
        if tipo not in {"activos", "firmaron", "nofirmaron", "tarde"}:
            return HttpResponseBadRequest("Tipo inválido")

        fecha = self._parse_fecha(request)
        data = self._compute_sets(fecha)

        pairs   = data[tipo]
        info    = data["info"]
        firmas  = data["firmas"]

        filas = []
        for key in pairs:
            did, uid = key
            meta = info.get(key)
            if not meta:
                nombre = f"Usuario {uid}"
                departamento = tipo_v = puesto = ""
            else:
                nombre = meta["nombre"]
                departamento = meta["departamento"]
                tipo_v = meta["tipo_vinculacion"]
                puesto = meta["puesto"]

            detalle = ""
            if tipo in {"firmaron", "tarde"}:
                ts = firmas.get(key)
                if ts:
                    ts_local = timezone.localtime(ts)
                    detalle = f"Primera firma: {ts_local.strftime('%H:%M')}"
                    if tipo == "tarde":
                        detalle += " (tarde)"
            if tipo == "nofirmaron":
                detalle = "Sin marcaje"
            if tipo == "activos" and not detalle:
                detalle = "Activo"

            filas.append(
                {
                    "nombre": nombre,
                    "departamento": departamento,
                    "tipo_vinculacion": tipo_v,
                    "puesto": puesto,
                    "detalle": detalle,
                }
            )

        filas.sort(key=lambda x: x["nombre"].lower())

        titulo_map = {
            "activos": "Empleados/usuarios activos (con dispositivo)",
            "firmaron": "Firmaron en el día",
            "nofirmaron": "No firmaron en el día",
            "tarde": "Llegadas tarde (> 09:05)",
        }

        ctx = {
            "fecha": fecha,
            "tipo": tipo,
            "titulo": titulo_map.get(tipo, ""),
            "filas": filas,
        }
        from django.shortcuts import render
        return render(request, self.template_name, ctx)

# ======================================================================================
# Reporte Ausencias del día (lista)
# ======================================================================================

class ReporteAusenciasView(View):
    """
    Ausentes: usuarios/empleados SIN ningún marcaje en la fecha.
    Nombre: empleado -> usuario_dispositivo.nombre -> user_id.
    """
    template_name = "reportes/ausencias.html"
    page_size = 30

    @staticmethod
    def _parse_fecha(s: str | None) -> date:
        return _parse_date_yyyy_mm_dd(s) or timezone.localdate()

    def get(self, request):
        fecha_raw = (request.GET.get("fecha") or "").strip()
        q = (request.GET.get("q") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()
        fecha = self._parse_fecha(fecha_raw)

        # Rango del día (timezone-aware)
        inicio = make_aware(datetime(fecha.year, fecha.month, fecha.day, 0, 0, 0))
        fin = make_aware(datetime(fecha.year, fecha.month, fecha.day, 23, 59, 59))

        # Base: SOLO usuarios de dispositivo activos, dispositivos activos y CON empleado
        uds = UsuarioDispositivo.objects.select_related("empleado", "dispositivo").filter(
            activo=True, dispositivo__activo=True, empleado__isnull=False
        )
        
        if depto:
            uds = uds.filter(empleado__departamento=depto)

        # Existe algún marcaje ese día
        asistencia_qs = AsistenciaCruda.objects.filter(
            dispositivo_id=OuterRef("dispositivo_id"),
            user_id=OuterRef("user_id"),
            ts__range=(inicio, fin),
        )

        # Ausentes = NO tienen ningún marcaje
        ausentes = uds.annotate(tiene_firma=Exists(asistencia_qs)).filter(tiene_firma=False)

        if q:
            ausentes = ausentes.filter(
                Q(empleado__nombre__icontains=q)
                | Q(empleado__apellido__icontains=q)
                | Q(nombre__icontains=q)
                | Q(user_id__icontains=q)
            )

        filas = []
        for u in ausentes:
            if u.empleado_id:
                nombre = f"{u.empleado.nombre} {u.empleado.apellido}".strip()
                depto = u.empleado.departamento or ""
                
                # Verificar si tiene baja autorizada para ese día
                baja = BajaAutorizada.objects.filter(
                    empleado_id=u.empleado_id,
                    fecha_inicio__lte=fecha,
                    fecha_fin__gte=fecha
                ).first()
                
                if baja:
                    estado = f"Baja Autorizada: {baja.get_tipo_display()}"
                else:
                    estado = "Sin entrada"
            else:
                nombre = (u.nombre or u.user_id or "").strip()
                depto = ""
                estado = "Sin entrada"
                
            filas.append({"fecha": fecha, "nombre": nombre, "departamento": depto, "estado": estado})

        filas.sort(key=lambda x: x["nombre"].lower() if x["nombre"] else "")
        page_obj = Paginator(filas, self.page_size).get_page(request.GET.get("page"))

        ctx = {
            "fecha": fecha.strftime("%Y-%m-%d"), 
            "q": q, 
            "page_obj": page_obj, 
            "total": len(filas),
            "departamentos": sorted([d for d in Empleado.objects.values_list("departamento", flat=True).distinct() if d]),
            "depto_sel": depto,
        }
        return render(request, self.template_name, ctx)


# ======================================================================================
# Reporte PDF: Totales de horas por persona en rango
# ======================================================================================

class NominaHorasFormView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/nomina_horas_form.html"

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        q = (request.GET.get("q") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()
        sort = (request.GET.get("sort") or "nombre").strip()
        order = (request.GET.get("order") or "asc").strip()
        pdf_view = NominaHorasPDFView()
        rows = pdf_view._compute_totals(d1, d2)
        departamentos = sorted({r["departamento"] for r in rows if r["departamento"]})
        rows = _filter_and_sort_rows(rows, q=q, depto=depto, sort=sort, order=order)

        # Formatear total de timedelta a HH:MM para la vista
        for r in rows:
            if isinstance(r.get("total"), timedelta):
                r["total"] = _hhmm(r["total"])

        ctx = {"inicio": d1, "fin": d2, "rows": rows, "q": q, "depto_sel": depto, "sort": sort, "order": order, "departamentos": departamentos}
        return render(request, self.template_name, ctx)


class NominaHorasPDFView(LoginRequiredMixin, StaffOnlyMixin, View):
    """
    PDF de totales por persona en el rango solicitado.
    Regla por día: si hay ≥2 marcajes, horas = max(ts) - min(ts); si no, 00:00.
    Identidad: Empleado si existe; si no, UsuarioDispositivo (nombre o user_id).
    """
    http_method_names = ["get", "head"]

    def head(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def _compute_totals(self, d1: date, d2: date) -> List[dict]:
        base = AsistenciaCruda.objects.filter(ts__date__gte=d1, ts__date__lte=d2)

        # Pares presentes para mapa UD
        pares = base.values_list("dispositivo_id", "user_id").distinct()
        mapa = _mapa_ud_para_pares(pares)

        # [MODIFICADO] Mapa de respaldo: buscar Empleado por (dispositivo_id, user_id)
        # Solo nos interesan los empleados. Fallback logic para usuarios sin empleado ELIMINADA.
        fallback_map = {}
        for emp in Empleado.objects.filter(activo=True, dispositivo__isnull=False).exclude(user_id=""):
            # emp.user_id es str, asegurar coincidencia
            k = (emp.dispositivo_id, emp.user_id)
            fallback_map[k] = {
                 "id": emp.id,
                 "nombre": emp.nombre_completo,
                 "departamento": emp.departamento,
                 "tipo": emp.get_tipo_vinculacion_display(), 
                 "puesto": emp.puesto,
            }

        # Agregado por día + identidad
        agg = (
            base.annotate(fecha=TruncDate("ts"))
            .values(
                "fecha", "dispositivo_id", "user_id",
                "usuario__nombre",
                "usuario__empleado_id",
                "usuario__empleado__nombre", "usuario__empleado__apellido",
                "usuario__empleado__departamento", "usuario__empleado__tipo_vinculacion",
                "usuario__empleado__puesto",
            )
            .annotate(entrada=Min("ts"), salida=Max("ts"), n=Count("id"))
        )

        totals: Dict[Tuple, dict] = {}
        for r in agg:
            entrada = r["entrada"]
            salida = r["salida"] if r["n"] >= 2 else None
            horas = (salida - entrada) if (entrada and salida and salida >= entrada) else timedelta(0)

            emp_id = r["usuario__empleado_id"]
            if emp_id:
                key = ("emp", emp_id)
                nombre = f"{r.get('usuario__empleado__nombre') or ''} {r.get('usuario__empleado__apellido') or ''}".strip() or "(sin nombre)"
                depto  = r.get("usuario__empleado__departamento") or ""
                tipo   = r.get("usuario__empleado__tipo_vinculacion") or ""
                puesto = r.get("usuario__empleado__puesto") or ""
            else:
                key = ("usr", r["dispositivo_id"], r["user_id"])
                
                # Intentar sacar info del mapa UD standard
                info = mapa.get((r["dispositivo_id"], r["user_id"]))
                
                found_emp = False
                if info and info.get("empleado_id"):
                    key = ("emp", info["empleado_id"])
                    nombre = f"{info.get('emp_nombre') or ''} {info.get('emp_apellido') or ''}".strip()
                    depto, tipo, puesto = info.get("depto") or "", info.get("tipo") or "", info.get("puesto") or ""
                    found_emp = True
                
                # Si no encontrado en UD, usar fallback
                elif not found_emp: # Changed to elif to be explicit
                    fb = fallback_map.get((r["dispositivo_id"], r["user_id"]))
                    if fb:
                        key = ("emp", fb["id"])
                        nombre = fb["nombre"] or "(sin nombre)"
                        depto = fb["departamento"] or ""
                        tipo = fb["tipo"] or "" # ya viene con display
                        puesto = fb["puesto"] or ""
                        found_emp = True # Mark as found

                # [MODIFICADO] Si sigue sin ser empleado, IGNORAR (continue)
                if not found_emp:
                    continue

            if key not in totals:
                totals[key] = {"nombre": nombre, "departamento": depto, "tipo": tipo, "puesto": puesto, "total": timedelta()}
            totals[key]["total"] += horas

        rows = sorted(totals.values(), key=lambda x: ((x["nombre"] or "").lower(), (x["departamento"] or "").lower()))
        return rows

    def _build_pdf(self, request, d1: date, d2: date, rows: List[dict]) -> HttpResponse:
        return build_pdf_nomina_horas(request, d1, d2, rows, _hhmm)


    def get(self, request, *args, **kwargs):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        if d1 > d2:
            return HttpResponseBadRequest("Rango inválido")

        q = (request.GET.get("q") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()
        sort = (request.GET.get("sort") or "nombre").strip()
        order = (request.GET.get("order") or "asc").strip()

        rows = self._compute_totals(d1, d2)
        rows = _filter_and_sort_rows(rows, q=q, depto=depto, sort=sort, order=order)

        return self._build_pdf(request, d1, d2, rows)


# ======================================================================================
# Reporte PDF: Ausencias totales (días) en rango excluyendo fines de semana
# ======================================================================================

class AusenciasTotalesFormView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/ausencias_totales_form.html"

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        q = (request.GET.get("q") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()
        sort = (request.GET.get("sort") or "nombre").strip()
        order = (request.GET.get("order") or "asc").strip()

        pdf_view = AusenciasTotalesPDFView()
        rows, total_dias = pdf_view._compute_rows(d1, d2)

        departamentos = sorted({r["departamento"] for r in rows if r["departamento"]})
        rows = _filter_and_sort_rows(rows, q=q, depto=depto, sort=sort, order=order)

        ctx = {
            "inicio": d1, "fin": d2, "rows": rows, "total_dias": total_dias,
            "q": q, "depto_sel": depto, "sort": sort, "order": order,
            "departamentos": departamentos,
        }
        return render(request, self.template_name, ctx)


class AusenciasTotalesPDFView(LoginRequiredMixin, StaffOnlyMixin, View):
    http_method_names = ["get", "head"]

    def head(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def _compute_rows(self, d1: date, d2: date) -> Tuple[List[dict], int]:
        tz = timezone.get_current_timezone()
        laborables_list, laborables_set = _laborables(d1, d2)
        total_dias = len(laborables_list)

        # 1) Roster base: empleados activos
        roster: Dict[Tuple, dict] = {}
        for emp in Empleado.objects.filter(activo=True).only("id", "nombre", "apellido", "departamento", "tipo_vinculacion", "puesto"):
            roster[("emp", emp.id)] = {
                "nombre": f"{emp.nombre or ''} {emp.apellido or ''}".strip() or "(sin nombre)",
                "departamento": emp.departamento or "",
                "tipo": emp.tipo_vinculacion or "",
                "puesto": emp.puesto or "",
                "presentes": set(),
            }

        # 2) [ELIMINADO] Usuarios sin empleado
        # Antes se buscaban usuarios "sueltos". Ahora se descartan por requerimiento.

        # 3) Días con presencia (solo laborables)
        presentes = (
            AsistenciaCruda.objects
            .filter(ts__date__gte=d1, ts__date__lte=d2)
            .annotate(fecha=TruncDate("ts", tzinfo=tz))
            .values("fecha", "usuario__empleado_id", "dispositivo_id", "user_id")
            .distinct()
        )
        for r in presentes:
            f = r["fecha"]
            if f not in laborables_set:
                continue
            # Solo procesar si tiene empleado asociado
            if r["usuario__empleado_id"]:
                key = ("emp", r["usuario__empleado_id"])
                if key in roster:
                    roster[key]["presentes"].add(f)

        # 4) Filas: ausencias = laborables - presentes
        rows = []
        for key, info in roster.items():
            dias_pres = len(info["presentes"])
            # Dias ausentes base
            dias_aus_bruto = max(total_dias - dias_pres, 0)
            
            # Contar bajas autorizadas en días laborables no presentes
            dias_baja = 0
            if key[0] == "emp":
                emp_id = key[1]
                ausencias_list = [d for d in laborables_list if d not in info["presentes"]]
                if ausencias_list:
                    dias_baja = BajaAutorizada.objects.filter(
                        empleado_id=emp_id,
                        fecha_inicio__lte=max(ausencias_list),
                        fecha_fin__gte=min(ausencias_list)
                    ).filter(
                        # Filtro manual para días exactos si es necesario, 
                        # pero por simplicidad y eficiencia usaremos una lógica de intersección
                    ).count()
                    
                    # Refinamiento: contar días exactos que son laborables Y están en el rango de alguna baja
                    bajas_obj = BajaAutorizada.objects.filter(
                        empleado_id=emp_id,
                        fecha_inicio__lte=d2,
                        fecha_fin__gte=d1
                    )
                    dias_baja_set = set()
                    for b in bajas_obj:
                        curr = max(b.fecha_inicio, d1)
                        last = min(b.fecha_fin, d2)
                        while curr <= last:
                            if curr in laborables_set and curr not in info["presentes"]:
                                dias_baja_set.add(curr)
                            curr += timedelta(days=1)
                    dias_baja = len(dias_baja_set)

            dias_aus_neto = max(dias_aus_bruto - dias_baja, 0)
            
            rows.append({
                "nombre": info["nombre"],
                "departamento": info["departamento"],
                "tipo": info["tipo"],
                "puesto": info["puesto"],
                "ausencias": dias_aus_neto,
                "bajas": dias_baja,
            })

        rows.sort(key=lambda x: (x["nombre"].lower(), x["departamento"].lower()))
        return rows, total_dias

    def _build_pdf(self, request, d1: date, d2: date, rows: List[dict]) -> HttpResponse:
        return build_pdf_ausencias_totales(request, d1, d2, rows)

    def get(self, request, *args, **kwargs):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        if d1 > d2:
            return HttpResponseBadRequest("Rango inválido")
            
        q = (request.GET.get("q") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()
        sort = (request.GET.get("sort") or "nombre").strip()
        order = (request.GET.get("order") or "asc").strip()

        rows, total_dias = self._compute_rows(d1, d2)
        rows = _filter_and_sort_rows(rows, q=q, depto=depto, sort=sort, order=order)

        return self._build_pdf(request, d1, d2, rows)

class SoloEntradaFormView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/solo_entrada_form.html"

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        q = (request.GET.get("q") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()
        sort = (request.GET.get("sort") or "nombre").strip()
        order = (request.GET.get("order") or "asc").strip()

        pdf_view = SoloEntradaPDFView()
        rows = pdf_view._compute_rows(d1, d2)

        departamentos = sorted({r["departamento"] for r in rows if r["departamento"]})
        rows = _filter_and_sort_rows(rows, q=q, depto=depto, sort=sort, order=order)

        ctx = {
            "inicio": d1, "fin": d2, "rows": rows, "q": q,
            "depto_sel": depto, "sort": sort, "order": order,
            "departamentos": departamentos,
        }
        return render(request, self.template_name, ctx)


class SoloEntradaPDFView(LoginRequiredMixin, StaffOnlyMixin, View):
    """
    Lista personas con conteo de días donde tuvieron exactamente 1 marcaje en el día.
    Identidad: Empleado si existe; si no, UsuarioDispositivo. Agrupa correctamente aunque un mismo usuario marque en varios dispositivos.
    """
    http_method_names = ["get", "head"]

    def head(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def _compute_rows(self, d1: date, d2: date):
        base = AsistenciaCruda.objects.filter(ts__date__gte=d1, ts__date__lte=d2)

        # Mapa UD para resolver identidad y metadatos
        pares = base.values_list("dispositivo_id", "user_id").distinct()
        mapa = _mapa_ud_para_pares(pares)

        # Agregado por día y usuario: n = cantidad de marcajes del día
        agg = (
            base.annotate(fecha=TruncDate("ts"))
            .values(
                "fecha",
                "dispositivo_id",
                "user_id",
                "usuario__nombre",
                "usuario__empleado_id",
                "usuario__empleado__nombre",
                "usuario__empleado__apellido",
                "usuario__empleado__departamento",
                "usuario__empleado__tipo_vinculacion",
                "usuario__empleado__puesto",
            )
            .annotate(n=Count("id"))
        )

        # Acumular: +1 si n==1 para ese día
        tot: Dict[Tuple, dict] = {}
        for r in agg:
            if r["n"] != 1:
                continue

            emp_id = r["usuario__empleado_id"]
            if emp_id:
                key = ("emp", emp_id)
                nombre = f"{r.get('usuario__empleado__nombre') or ''} {r.get('usuario__empleado__apellido') or ''}".strip() or "(sin nombre)"
                depto  = r.get("usuario__empleado__departamento") or ""
                tipo   = r.get("usuario__empleado__tipo_vinculacion") or ""
                puesto = r.get("usuario__empleado__puesto") or ""
            else:
                key = ("usr", r["dispositivo_id"], r["user_id"])
                info = mapa.get((r["dispositivo_id"], r["user_id"]))
                if info and info.get("empleado_id"):
                    key = ("emp", info["empleado_id"])
                    nombre = f"{info.get('emp_nombre') or ''} {info.get('emp_apellido') or ''}".strip()
                    depto, tipo, puesto = info.get("depto") or "", info.get("tipo") or "", info.get("puesto") or ""
                else:
                    # [MODIFICADO] Ignorar usuarios sin empleado
                    continue

            if key not in tot:
                tot[key] = {"nombre": nombre, "departamento": depto, "tipo": tipo, "puesto": puesto, "dias_solo_entrada": 0}
            tot[key]["dias_solo_entrada"] += 1

        rows = sorted(tot.values(), key=lambda x: ((x["nombre"] or "").lower(), (x["departamento"] or "").lower()))
        return rows

    def _build_pdf(self, request, d1: date, d2: date, rows):
        return build_pdf_solo_entrada(request, d1, d2, rows)

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        if d1 > d2:
            return HttpResponseBadRequest("Rango inválido")

        q = (request.GET.get("q") or "").strip()
        depto = (request.GET.get("departamento") or "").strip()
        sort = (request.GET.get("sort") or "nombre").strip()
        order = (request.GET.get("order") or "asc").strip()

        rows = self._compute_rows(d1, d2)
        rows = _filter_and_sort_rows(rows, q=q, depto=depto, sort=sort, order=order)

        return self._build_pdf(request, d1, d2, rows)

class ReporteEmpleadoFormView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/rep_empleado_form.html"

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")

        # Empleados activos
        empleados_qs = (
            Empleado.objects.filter(activo=True)
            .order_by("apellido", "nombre")
            .values("id", "nombre", "apellido", "departamento", "puesto")
        )

        # Usuarios de dispositivo activos SIN empleado asociado
        uds_qs = (
            UsuarioDispositivo.objects
            .filter(activo=True, dispositivo__activo=True, empleado__isnull=True)
            .values("dispositivo_id", "user_id", "nombre")
            .order_by("nombre", "user_id")
        )

        personas = []

        # Empleados -> valor emp-<id>
        for e in empleados_qs:
            label = f"{e['apellido']}, {e['nombre']}"
            if e["departamento"]:
                label += f" — {e['departamento']}"
            if e["puesto"]:
                label += f" — {e['puesto']}"
            personas.append({
                "value": f"emp-{e['id']}",
                "label": label,
            })

        # [MODIFICADO] Loop de Usuarios "usr-..." eliminado por requerimiento.
        # Solo se muestran empleados.

        # Orden alfabético por etiqueta
        personas.sort(key=lambda x: x["label"].lower())

        ctx = {"inicio": d1, "fin": d2, "personas": personas}
        return render(request, self.template_name, ctx)


class ReporteEmpleadoPDFView(LoginRequiredMixin, StaffOnlyMixin, View):
    """
    PDF por trabajador/usuario: lista día a día del período con entrada, salida y total.
    - Si solo hay 1 marcaje en el día, salida en blanco y total 00:00.
    - Soporta:
        * Empleado (valor emp-<id>)
        * Usuario de dispositivo sin empleado (valor usr-<dispositivo_id>:<user_id>)
    """

    http_method_names = ["get", "head"]

    def head(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def _parse_params(self, request):
        """
        Devuelve: (d1, d2, kind, emp_id, did, uid)
        kind: "emp" o "usr" o None si algo no es válido.
        """
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        raw = (request.GET.get("empleado") or "").strip()

        kind = None
        emp_id = None
        did = None
        uid = None

        if raw:
            if raw.startswith("emp-"):
                kind = "emp"
                try:
                    emp_id = int(raw[4:])
                except ValueError:
                    kind = None
            elif raw.startswith("disabled_usr_"):
                kind = "usr"
                data = raw[4:]
                try:
                    did_str, uid = data.split(":", 1)
                    did = int(did_str)
                except Exception:
                    kind = None

        return d1, d2, kind, emp_id, did, uid

    def _rows_for_person(
        self,
        d1: date,
        d2: date,
        kind: str,
        emp_id: int | None = None,
        did: int | None = None,
        uid: str | None = None,
    ):
        """
        Devuelve (rows, meta)
        meta: {nombre, departamento, tipo, puesto}
        rows: [{fecha, entrada, salida, total}]
        """
        base = AsistenciaCruda.objects.filter(ts__date__gte=d1, ts__date__lte=d2)

        meta = {
            "nombre": "",
            "departamento": "",
            "tipo": "",
            "puesto": "",
        }

        if kind == "emp" and emp_id:
            # Pre-cargar metadatos desde Empleado
            emp = (
                Empleado.objects.filter(pk=emp_id)
                .values("nombre", "apellido", "departamento", "tipo_vinculacion", "puesto")
                .first()
            )
            if emp:
                meta["nombre"] = f"{emp['nombre']} {emp['apellido']}".strip() or "(sin nombre)"
                meta["departamento"] = emp.get("departamento") or ""
                meta["tipo"] = emp.get("tipo_vinculacion") or ""
                meta["puesto"] = emp.get("puesto") or ""

            # registros del rango para ese empleado, incluyendo UD sin FK directa
            ud_exists = UsuarioDispositivo.objects.filter(
                empleado_id=emp_id,
                dispositivo_id=OuterRef("dispositivo_id"),
                user_id=OuterRef("user_id"),
            )
            base = base.filter(Q(usuario__empleado_id=emp_id) | Exists(ud_exists))

            agg = (
                base.annotate(fecha=TruncDate("ts"))
                .values(
                    "fecha",
                    "usuario__empleado__nombre",
                    "usuario__empleado__apellido",
                    "usuario__empleado__departamento",
                    "usuario__empleado__tipo_vinculacion",
                    "usuario__empleado__puesto",
                )
                .annotate(entrada=Min("ts"), salida=Max("ts"), n=Count("id"))
                .order_by("fecha")
            )

        elif kind == "usr" and did is not None and uid is not None:
            # Solo los marcajes de ese usuario+dispositivo
            base = base.filter(dispositivo_id=did, user_id=uid)

            agg = (
                base.annotate(fecha=TruncDate("ts"))
                .values("fecha")
                .annotate(entrada=Min("ts"), salida=Max("ts"), n=Count("id"))
                .order_by("fecha")
            )

            # Metadatos desde UsuarioDispositivo (sin empleado)
            ud = (
                UsuarioDispositivo.objects
                .filter(dispositivo_id=did, user_id=uid)
                .only("nombre", "user_id")
                .first()
            )
            meta["nombre"] = (ud.nombre if ud else "") or f"Usuario {uid}"
            # dept, tipo y puesto se quedan vacíos

        else:
            return [], meta

        rows: list[dict] = []
        for r in agg:
            entrada = r["entrada"]
            if entrada:
                entrada = timezone.localtime(entrada)
            
            salida = r["salida"] if r["n"] >= 2 else None
            if salida:
                salida = timezone.localtime(salida)

            total = (salida - entrada) if (entrada and salida and salida >= entrada) else timedelta(0)

            # Si es empleado y aún no teníamos meta rellenado (por ejemplo, no se encontró el Empleado)
            if kind == "emp" and not meta["nombre"]:
                nombre = f"{(r.get('usuario__empleado__nombre') or '').strip()} {(r.get('usuario__empleado__apellido') or '').strip()}".strip()
                meta["nombre"] = nombre or "(sin nombre)"
                meta["departamento"] = r.get("usuario__empleado__departamento") or ""
                meta["tipo"] = r.get("usuario__empleado__tipo_vinculacion") or ""
                meta["puesto"] = r.get("usuario__empleado__puesto") or ""

            rows.append(
                {
                    "fecha": r["fecha"],
                    "entrada": entrada,
                    "salida": salida,
                    "total": total,
                }
            )

        return rows, meta

    def _build_pdf(self, request, d1: date, d2: date, meta: dict, rows):
        return build_pdf_reporte_empleado(request, d1, d2, meta, rows, _hhmm)


    def get(self, request):
        d1, d2, kind, emp_id, did, uid = self._parse_params(request)
        if not kind:
            return HttpResponseBadRequest("Debe seleccionar un empleado o usuario.")
        if d1 > d2:
            return HttpResponseBadRequest("Rango inválido.")
        rows, meta = self._rows_for_person(d1, d2, kind, emp_id, did, uid)
        return self._build_pdf(request, d1, d2, meta, rows)


class RepAusenciasEmpleadoFormView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/rep_ausencias_empleado_form.html"

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")

        # Empleados activos
        empleados_qs = (
            Empleado.objects.filter(activo=True)
            .order_by("apellido", "nombre")
            .values("id", "nombre", "apellido", "departamento", "puesto")
        )

        # Usuarios de dispositivo activos SIN empleado asociado
        uds_qs = (
            UsuarioDispositivo.objects
            .filter(activo=True, dispositivo__activo=True, empleado__isnull=True)
            .values("dispositivo_id", "user_id", "nombre")
            .order_by("nombre", "user_id")
        )

        personas = []

        # Empleados -> valor emp-<id>
        for e in empleados_qs:
            label = f"{e['apellido']}, {e['nombre']}"
            if e["departamento"]:
                label += f" — {e['departamento']}"
            if e["puesto"]:
                label += f" — {e['puesto']}"
            personas.append({
                "value": f"emp-{e['id']}",
                "label": label,
            })

        # [MODIFICADO] Loop de Usuarios "usr-..." eliminado por requerimiento.
        # Solo se muestran empleados.

        personas.sort(key=lambda x: x["label"].lower())

        ctx = {"inicio": d1, "fin": d2, "personas": personas}
        return render(request, self.template_name, ctx)


class RepAusenciasEmpleadoPDFView(LoginRequiredMixin, StaffOnlyMixin, View):
    """
    PDF por trabajador/usuario: lista los días laborables del período en los que NO tuvo
    ningún marcaje (ausencias). Se excluyen sábados y domingos.
    """

    http_method_names = ["get", "head"]

    def head(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def _parse_params(self, request):
        """
        Devuelve: (d1, d2, kind, emp_id, did, uid)
        kind: "emp" o "usr" o None si algo no es válido.
        """
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        raw = (request.GET.get("empleado") or "").strip()

        kind = None
        emp_id = None
        did = None
        uid = None

        if raw:
            if raw.startswith("emp-"):
                kind = "emp"
                try:
                    emp_id = int(raw[4:])
                except ValueError:
                    kind = None
            elif raw.startswith("disabled_usr_"):
                kind = "usr"
                data = raw[4:]
                try:
                    did_str, uid = data.split(":", 1)
                    did = int(did_str)
                except Exception:
                    kind = None

        return d1, d2, kind, emp_id, did, uid

    def _rows_for_person(
        self,
        d1: date,
        d2: date,
        kind: str,
        emp_id: int | None = None,
        did: int | None = None,
        uid: str | None = None,
    ):
        """
        Devuelve (rows, meta, total_laborables)
        rows: [{fecha}]
        meta: {nombre, departamento, tipo, puesto}
        """
        tz = timezone.get_current_timezone()
        laborables_list, laborables_set = _laborables(d1, d2)
        total_laborables = len(laborables_list)

        meta = {
            "nombre": "",
            "departamento": "",
            "tipo": "",
            "puesto": "",
        }

        base = AsistenciaCruda.objects.filter(ts__date__gte=d1, ts__date__lte=d2)

        if kind == "emp" and emp_id:
            # Metadatos desde Empleado
            emp = (
                Empleado.objects.filter(pk=emp_id)
                .values("nombre", "apellido", "departamento", "tipo_vinculacion", "puesto")
                .first()
            )
            if emp:
                meta["nombre"] = f"{emp['nombre']} {emp['apellido']}".strip() or "(sin nombre)"
                meta["departamento"] = emp.get("departamento") or ""
                meta["tipo"] = emp.get("tipo_vinculacion") or ""
                meta["puesto"] = emp.get("puesto") or ""

            # Presencia para ese empleado (incluyendo UD vinculado)
            ud_exists = UsuarioDispositivo.objects.filter(
                empleado_id=emp_id,
                dispositivo_id=OuterRef("dispositivo_id"),
                user_id=OuterRef("user_id"),
            )
            base = base.filter(Q(usuario__empleado_id=emp_id) | Exists(ud_exists))

            presentes_qs = (
                base.annotate(fecha=TruncDate("ts", tzinfo=tz))
                .values("fecha")
                .distinct()
            )

        elif kind == "usr" and did is not None and uid is not None:
            # Solo marcajes de ese usuario+dispositivo
            base = base.filter(dispositivo_id=did, user_id=uid)
            presentes_qs = (
                base.annotate(fecha=TruncDate("ts", tzinfo=tz))
                .values("fecha")
                .distinct()
            )
            # Metadatos básicos desde UD
            ud = (
                UsuarioDispositivo.objects
                .filter(dispositivo_id=did, user_id=uid)
                .only("nombre", "user_id")
                .first()
            )
            meta["nombre"] = (ud.nombre if ud else "") or f"Usuario {uid}"
        else:
            return [], meta, total_laborables

        # Conjunto de días con presencia (solo laborables)
        presentes = {r["fecha"] for r in presentes_qs if r["fecha"] in laborables_set}

        # Días de ausencia = laborables sin presencia
        rows = []
        for f in laborables_list:
            if f not in presentes:
                # Verificar si tiene baja autorizada para ese día
                baja = None
                if kind == "emp" and emp_id:
                    baja = BajaAutorizada.objects.filter(
                        empleado_id=emp_id,
                        fecha_inicio__lte=f,
                        fecha_fin__gte=f
                    ).first()
                
                rows.append({
                    "fecha": f,
                    "estado": f"Baja Autorizada: {baja.get_tipo_display()}" if baja else "Sin marcaje"
                })

        return rows, meta, total_laborables

    def _build_pdf(self, request, d1: date, d2: date, meta: dict, rows, total_laborables: int):
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
            body_rows.append([fecha_txt, r["estado"]])

        # Fila de totales al final
        body_rows.append(["TOTAL", f"{total_ausencias} días"])

        table = _tabla_estilizada(
            headers=["Fecha", "Estado"],
            rows=body_rows,
            col_widths=[40 * mm, 80 * mm],
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

    def get(self, request):
        d1, d2, kind, emp_id, did, uid = self._parse_params(request)
        if not kind:
            return HttpResponseBadRequest("Debe seleccionar un empleado o usuario.")
        if d1 > d2:
            return HttpResponseBadRequest("Rango inválido.")
        rows, meta, total_laborables = self._rows_for_person(d1, d2, kind, emp_id, did, uid)
        return self._build_pdf(request, d1, d2, meta, rows, total_laborables)


# ======================================================================================
# Nómina: Cálculo Salarial
# ======================================================================================

class NominaCalculoFormView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/nomina_calculo_form.html"

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        return render(request, self.template_name, {"inicio": d1, "fin": d2})


class NominaCalculoPDFView(LoginRequiredMixin, StaffOnlyMixin, View):
    """
    Cálculo de salario mensual:
    1) Salario Base (del Empleado).
    2) Días Laborables en el periodo.
    3) Ausencias (laborables sin marcajes ni baja autorizada).
    4) Descuento = (SalarioBase / d_laborables_mes) * d_ausencia.
    5) Neto = SalarioBase - Descuento.
    """
    http_method_names = ["get", "head"]

    def head(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def _compute_nomina(self, d1: date, d2: date) -> List[dict]:
        laborables_list, laborables_set = _laborables(d1, d2)
        total_laborables = len(laborables_list)
        if total_laborables == 0:
            return []

        # 1) Empleados con salario base
        empleados = Empleado.objects.filter(activo=True).only(
            "id", "nombre", "apellido", "departamento", "salario_base"
        )
        
        # 2) Presencia en el rango
        presentes_qs = (
            AsistenciaCruda.objects.filter(ts__date__gte=d1, ts__date__lte=d2)
            .values("usuario__empleado_id", "dispositivo_id", "user_id", "ts__date")
            .distinct()
        )
        mapa_presencia: Dict[int, set] = {}
        # También necesitamos mapear did, uid a empleado_id para casos sin FK
        mapa_ud_emp = {
            (ud.dispositivo_id, ud.user_id): ud.empleado_id
            for ud in UsuarioDispositivo.objects.filter(empleado__isnull=False)
        }

        for r in presentes_qs:
            eid = r["usuario__empleado_id"]
            if not eid:
                eid = mapa_ud_emp.get((r["dispositivo_id"], r["user_id"]))
            if eid:
                if eid not in mapa_presencia:
                    mapa_presencia[eid] = set()
                mapa_presencia[eid].add(r["ts__date"])

        # 3) Bajas autorizadas
        bajas_qs = BajaAutorizada.objects.filter(fecha_inicio__lte=d2, fecha_fin__gte=d1)
        mapa_bajas: Dict[int, set] = {}
        for b in bajas_qs:
            eid = b.empleado_id
            if eid not in mapa_bajas:
                mapa_bajas[eid] = set()
            curr = max(b.fecha_inicio, d1)
            last = min(b.fecha_fin, d2)
            while curr <= last:
                if curr in laborables_set:
                    mapa_bajas[eid].add(curr)
                curr += timedelta(days=1)

        rows = []
        for emp in empleados:
            eid = emp.id
            pres = mapa_presencia.get(eid, set())
            bajas = mapa_bajas.get(eid, set())
            
            # Ausencias a descontar = laborables - pres - bajas
            ausencias = [d for d in laborables_list if d not in pres and d not in bajas]
            num_aus = len(ausencias)
            
            sal_base = float(emp.salario_base)
            if sal_base > 0:
                costo_dia = sal_base / total_laborables # Simplificación: laborables del periodo
                descuento = costo_dia * num_aus
                neto = sal_base - descuento
            else:
                descuento = 0
                neto = 0

            rows.append({
                "id": eid,
                "nombre": emp.nombre_completo,
                "departamento": emp.departamento,
                "salario_base": sal_base,
                "ausencias": num_aus,
                "bajas": len(bajas),
                "descuento": descuento,
                "neto": neto,
            })
        
        print(f"[DEBUG] Computed rows: {len(rows)}")
        for r in rows:
            print(f" -> Emp: {r['nombre']} (ID {r['id']}) | Base: {r['salario_base']} | Aus: {r['ausencias']} | Desc: {r['descuento']} | Neto: {r['neto']}")

        return sorted(rows, key=lambda x: x["nombre"].lower())

    def _build_pdf(self, request, d1: date, d2: date, rows: List[dict]) -> HttpResponse:
        return build_pdf_nomina_calculo(request, d1, d2, rows)

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        if d1 > d2:
            return HttpResponseBadRequest("Rango inválido")
        rows = self._compute_nomina(d1, d2)
        return self._build_pdf(request, d1, d2, rows)

from .models import NominaPeriodo, NominaEmpleado

class NominaCalculoPreviewView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/nomina_preview.html"

    def get(self, request):
        d1, d2 = _parse_rango_request(request, "inicio", "fin")
        if d1 > d2:
            return HttpResponseBadRequest("Rango inválido")
        
        # Obtener lógica de cálculo
        calc_view = NominaCalculoPDFView()
        rows = calc_view._compute_nomina(d1, d2)
        
        ctx = {
            "inicio": d1,
            "fin": d2,
            "rows": rows,
            "total_empleados": len(rows),
        }
        return render(request, self.template_name, ctx)

class NominaGuardarView(LoginRequiredMixin, StaffOnlyMixin, View):
    @transaction.atomic
    def post(self, request):
        inicio_str = request.POST.get("inicio")
        fin_str = request.POST.get("fin")
        d1 = _parse_date_yyyy_mm_dd(inicio_str)
        d2 = _parse_date_yyyy_mm_dd(fin_str)
        
        if not d1 or not d2:
            messages.error(request, "Fechas inválidas.")
            return redirect("reportes:nomina_calculo_form")

        # Crear o actualizar el periodo
        periodo, _ = NominaPeriodo.objects.get_or_create(
            inicio=d1, fin=d2,
            defaults={"nota": f"Nómina generada el {datetime.now().strftime('%d/%m/%Y')}"}
        )
        
        # Procesar cada empleado
        emp_ids = request.POST.getlist("emp_id")
        for eid in emp_ids:
            try:
                emp = Empleado.objects.get(pk=eid)
                
                # Helper para limpiar formato (ej: 500.000 -> 500000)
                def _limpiar_moneda(val):
                    if not val: return 0
                    # Si viene como 500.000, quitamos los puntos
                    clean = str(val).replace(".", "").replace(" FCFA", "").strip()
                    # Si por error usaron comas decimales, las manejamos (aunque pedimos enteros)
                    clean = clean.replace(",", ".")
                    try:
                        return float(clean)
                    except ValueError:
                        return 0

                # Extraer valores del POST
                salario_base = _limpiar_moneda(request.POST.get(f"salario_base_{eid}", "0"))
                dias_ausencia = int(request.POST.get(f"ausencias_{eid}", "0"))
                descuento_ausencia = _limpiar_moneda(request.POST.get(f"descuento_ausencia_{eid}", "0"))
                bonos = _limpiar_moneda(request.POST.get(f"bonos_{eid}", "0"))
                otros = _limpiar_moneda(request.POST.get(f"otros_{eid}", "0"))
                desc = _limpiar_moneda(request.POST.get(f"desc_{eid}", "0"))
                imp = _limpiar_moneda(request.POST.get(f"imp_{eid}", "0"))

                NominaEmpleado.objects.update_or_create(
                    periodo=periodo,
                    empleado=emp,
                    defaults={
                        "salario_base": salario_base,
                        "dias_ausencia": dias_ausencia,
                        "monto_descuento_ausencia": descuento_ausencia,
                        "bonos": bonos,
                        "otros_ingresos": otros,
                        "descuentos": desc,
                        "impuestos": imp,
                        "neto_pagar": 0, # Se calcula en el save() del modelo
                    }
                )
            except Empleado.DoesNotExist:
                continue

        periodo.finalizado = True
        periodo.save()
        
        messages.success(request, f"Nómina para el periodo {d1} - {d2} guardada correctamente.")
        return redirect("reportes:nomina_calculo_form")

class NominaArchivoView(LoginRequiredMixin, StaffOnlyMixin, View):
    template_name = "reportes/nomina_archivo.html"

    def get(self, request):
        # Obtener todos los periodos finalizados
        periodos = NominaPeriodo.objects.filter(finalizado=True).order_by("-inicio")
        
        # Agrupar por Año -> Mes
        # Estructura: { 2024: { 1: [p1, p2], 2: [p3] }, 2023: ... }
        archivo = {}
        for p in periodos:
            year = p.inicio.year
            month = p.inicio.month
            
            if year not in archivo:
                archivo[year] = {}
            if month not in archivo[year]:
                archivo[year][month] = []
            
            archivo[year][month].append(p)
            
        return render(request, self.template_name, {"archivo": archivo})
