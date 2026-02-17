from django.urls import path
from . import views

app_name = "empleados"

urlpatterns = [
    # Empleados
    path("", views.empleado_list, name="list"),
    path("nuevo/", views.empleado_crear, name="crear"),
    path("<int:pk>/", views.empleado_detalle, name="detalle"),
    path("<int:pk>/editar/", views.empleado_editar, name="editar"),
    path("<int:pk>/vincular/", views.empleado_vincular, name="vincular"),
    path("desvincular/<int:pk>/", views.empleado_desvincular, name="desvincular"),
    path("ajax/load-users/", views.load_users, name="ajax_load_users"),
    path("<int:pk>/crear-en-equipo/", views.empleado_crear_en_equipo, name="crear_en_equipo"),
    
    # Documentos (Empleado)
    path("<int:emp_id>/documento/subir/", views.documento_subir_empleado, name="doc_subir_empleado"),
    path("documento/<int:pk>/eliminar/", views.documento_eliminar, name="doc_eliminar"),

    # Bajas Autorizadas
    path("<int:emp_id>/baja/nueva/", views.baja_crear, name="baja_crear"),
    path("baja/<int:pk>/eliminar/", views.baja_eliminar, name="baja_eliminar"),

    # Cantera (Candidatos)
    path("cantera/", views.candidato_list, name="candidato_list"),
    path("cantera/nuevo/", views.candidato_crear, name="candidato_crear"),
    path("cantera/<int:pk>/", views.candidato_detalle, name="candidato_detalle"),
    path("cantera/<int:pk>/editar/", views.candidato_editar, name="candidato_editar"),
    path("cantera/<int:pk>/promover/", views.candidato_promover, name="candidato_promover"),
    
    # Documentos (Candidato)
    path("cantera/<int:cand_id>/documento/subir/", views.documento_subir_candidato, name="doc_subir_candidato"),
]
