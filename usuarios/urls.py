from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('', views.listar_usuarios, name='listar'),
    path('crear/', views.crear_usuario, name='crear'),
    path('editar/<int:user_id>/', views.editar_usuario, name='editar'),
    path('eliminar/<int:user_id>/', views.eliminar_usuario, name='eliminar'),
    path('resetear-password/<int:user_id>/', views.resetear_password, name='resetear_password'),
    path('cambiar-password/', views.cambiar_password, name='cambiar_password'),
]
