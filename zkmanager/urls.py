from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView
from reportes.views import dashboard
from .views import logout_now

urlpatterns = [
    path("admin/", admin.site.urls),

    # Login propio -> al autenticar va a LOGIN_REDIRECT_URL (/dashboard/)
    path(
        "login/",
        LoginView.as_view(
            template_name="login.html",
            redirect_authenticated_user=True
        ),
        name="login",
    ),

    path("logout/", logout_now, name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("config/", include(("dispositivos.urls","config"), namespace="config")),
    path("empleados/", include(("empleados.urls","empleados"), namespace="empleados")),
    path("reportes/", include("reportes.urls", namespace="reportes")),
    path("", dashboard),
]
