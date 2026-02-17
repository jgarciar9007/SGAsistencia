from django.urls import path
from . import views

app_name = "config"

urlpatterns = [
    path("", views.config_index, name="index"),
    
          # Gestión de Dispositivos
    path("dispositivo/nuevo/", views.dispositivo_crear, name="dispositivo_crear"),
    path("dispositivo/<int:pk>/editar/", views.dispositivo_editar, name="dispositivo_editar"),
    path("dispositivo/<int:pk>/eliminar/", views.dispositivo_eliminar, name="dispositivo_eliminar"),
    path("dispositivo/<int:pk>/probar/", views.dispositivo_probar_conexion, name="dispositivo_probar"),
    path("dispositivo/<int:pk>/usuarios/", views.descargar_usuarios, name="descargar_usuarios"),
    path("dispositivo/<int:pk>/asistencia/", views.descargar_asistencia, name="descargar_asistencia"),


    



        # Reportes de Asistencia por Dispositivo
    path("asistencias/", views.asistencia_list, name="asistencia_list"),
    path("asistencias/export/csv/", views.asistencia_export_csv, name="asistencia_export_csv"),

        # Reportes de Usuarios
    path("usuarios/", views.usuario_list, name="usuario_list"),
    path("usuarios/export/csv/", views.usuario_export_csv, name="usuario_export_csv"),
    path("reportes/asistencia/", views.reporte_asistencia, name="reporte_asistencia"),

]
