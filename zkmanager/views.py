from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from datetime import datetime, timedelta
from django.views import View
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Min, Max, Count, Q
from django.db.models.functions import TruncDate
from dispositivos.models import AsistenciaCruda
from empleados.models import Empleado



class ReporteAsistenciaGeneralView(View):
    """
    Reporte general de asistencia (por empleado y día).
    - Sin filtro de dispositivo.
    - Entrada: primer marcaje del día.
    - Salida: último marcaje del día. Si solo hay 1 marcaje, se deja salida = "Sin firma".
    - Horas trabajadas: salida - entrada; si falta alguno -> 0.
    """
    template_name = "reportes/asistencia_general.html"
    page_size = 30

    @staticmethod
    def _parse_fecha(s, end=False):
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
        # Filtros básicos
        desde_raw = (request.GET.get("desde") or "").strip()
        hasta_raw = (request.GET.get("hasta") or "").strip()
        q = (request.GET.get("q") or "").strip()
        empleado_id = (request.GET.get("empleado") or "").strip()

        hoy = datetime.now().date()
        if not desde_raw and not hasta_raw:
            desde_raw = hoy.strftime("%Y-%m-%d")
            hasta_raw = hoy.strftime("%Y-%m-%d")

        desde = self._parse_fecha(desde_raw)
        hasta = self._parse_fecha(hasta_raw, end=True)

        # Base: solo marcajes con empleado vinculado
        base = (AsistenciaCruda.objects
                .filter(usuario__empleado__isnull=False))

        if desde:
            base = base.filter(ts__gte=desde)
        if hasta:
            base = base.filter(ts__lte=hasta)

        if empleado_id.isdigit():
            base = base.filter(usuario__empleado_id=int(empleado_id))

        if q:
            base = base.filter(
                Q(usuario__empleado__nombre__icontains=q) |
                Q(usuario__empleado__apellido__icontains=q) |
                Q(usuario__empleado__numero__icontains=q) |
                Q(usuario__empleado__doc_id__icontains=q)
            )

        # Agregado por empleado + día
        agg = (base
               .annotate(fecha=TruncDate("ts"))
               .values(
                   "fecha",
                   "usuario__empleado_id",
                   "usuario__empleado__nombre",
                   "usuario__empleado__apellido",
                   "usuario__empleado__departamento",
               )
               .annotate(
                   entrada=Min("ts"),
                   salida=Max("ts"),
                   n=Count("id"),
               )
               .order_by("fecha", "usuario__empleado__apellido", "usuario__empleado__nombre"))

        # Construcción de filas
        filas = []
        for r in agg:
            entrada = r["entrada"]
            salida = r["salida"] if r["n"] >= 2 else None  # con 1 marcaje, consideramos sin salida
            if entrada and salida and salida >= entrada:
                horas = salida - entrada
            else:
                horas = timedelta(0)

            filas.append({
                "fecha": r["fecha"],
                "empleado_id": r["usuario__empleado_id"],
                "nombre": f'{r["usuario__empleado__nombre"]} {r["usuario__empleado__apellido"]}'.strip(),
                "departamento": r["usuario__empleado__departamento"] or "",
                "entrada": entrada or "Sin firma",
                "salida": salida or "Sin firma",
                "total_horas": horas,
            })

        # Paginación
        paginator = Paginator(filas, self.page_size)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        # Catálogo de empleados para filtro opcional
        empleados = Empleado.objects.filter(activo=True).order_by("apellido", "nombre").values("id", "nombre", "apellido")

        ctx = {
            "desde": desde_raw,
            "hasta": hasta_raw,
            "q": q,
            "empleado": int(empleado_id) if empleado_id.isdigit() else "",
            "page_obj": page_obj,
            "total": len(filas),
            "empleados": empleados,
        }
        return render(request, self.template_name, ctx)



@require_GET
def logout_now(request):
    logout(request)
    request.session.flush()
    return redirect("/login/")
