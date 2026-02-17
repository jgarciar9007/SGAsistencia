from django.urls import path
from .views import (
    ReporteAsistenciaGeneralView,
    ReporteAusenciasView,
    NominaHorasFormView,
    NominaHorasPDFView,
    AusenciasTotalesFormView,   # <- importar
    AusenciasTotalesPDFView,  
    ReporteEmpleadoFormView,
    ReporteEmpleadoPDFView,
    RepAusenciasEmpleadoFormView,
    RepAusenciasEmpleadoPDFView,  # <- importar
    NominaCalculoFormView,
    NominaCalculoPDFView,
    NominaCalculoPreviewView,
    NominaGuardarView,
    NominaArchivoView,
)
from .views import SoloEntradaFormView, SoloEntradaPDFView, DashboardListView

app_name = "reportes"

urlpatterns = [
    path("asistencia/",           ReporteAsistenciaGeneralView.as_view(), name="asistencia_general"),
    path("ausencias/",            ReporteAusenciasView.as_view(),         name="ausencias"),
    path("nomina/horas/",         NominaHorasFormView.as_view(),          name="nomina_horas_form"),
    path("nomina/horas/pdf/",     NominaHorasPDFView.as_view(),           name="nomina_horas_pdf"),
    path("nomina/ausencias/",     AusenciasTotalesFormView.as_view(),     name="ausencias_totales_form"),
    path("nomina/ausencias/pdf/", AusenciasTotalesPDFView.as_view(),      name="ausencias_totales_pdf"),
    path("nomina/solo-entrada/",     SoloEntradaFormView.as_view(), name="solo_entrada_form"),
    path("nomina/solo-entrada/pdf/", SoloEntradaPDFView.as_view(),  name="solo_entrada_pdf"),
    # Reportes de Asistencia por Empleado
    path("trabajador/asistencia/",     ReporteEmpleadoFormView.as_view(), name="rep_empleado_form"),
    path("trabajador/asistencia/pdf/", ReporteEmpleadoPDFView.as_view(),  name="rep_empleado_pdf"),
    # Reportes de Ausencias por Empleado
    path("trabajador/ausencias/",      RepAusenciasEmpleadoFormView.as_view(), name="rep_ausencias_empleado_form"),
    path("trabajador/ausencias/pdf/",  RepAusenciasEmpleadoPDFView.as_view(),  name="rep_ausencias_empleado_pdf"),
      path(
        "dashboard/listado/<str:tipo>/",
        DashboardListView.as_view(),
        name="dashboard_listado",
    ),
    path("nomina/calculo/",       NominaCalculoFormView.as_view(),        name="nomina_calculo_form"),
    path("nomina/calculo/pdf/",   NominaCalculoPDFView.as_view(),         name="nomina_calculo_pdf"),
    path("nomina/preview/",       NominaCalculoPreviewView.as_view(),     name="nomina_preview"),
    path("nomina/guardar/",       NominaGuardarView.as_view(),            name="nomina_guardar"),
    path("nomina/historico/",     NominaArchivoView.as_view(),            name="nomina_archivo"),
]
