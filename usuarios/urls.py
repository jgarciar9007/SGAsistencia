from django.urls import path
from . import views

app_name = "usuarios"

urlpatterns = [
    path("", views.UserListView.as_view(), name="lista"),
    path("nuevo/", views.UserCreateView.as_view(), name="crear"),
    path("<int:pk>/editar/", views.UserUpdateView.as_view(), name="editar"),
    path("<int:pk>/eliminar/", views.UserDeleteView.as_view(), name="eliminar"),
    path("cambiar-password/", views.PasswordChangeCustomView.as_view(), name="cambiar_password"),
]
