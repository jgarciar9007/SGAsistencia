from django.db import models
from django.contrib.auth.models import User

class PerfilUsuario(models.Model):
    """
    Perfil extendido para usuarios del sistema
    Permite asignar roles y permisos adicionales
    """
    ROLES = [
        ('admin', 'Administrador'),
        ('supervisor', 'Supervisor'),
        ('rrhh', 'Recursos Humanos'),
        ('operador', 'Operador'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol = models.CharField(max_length=20, choices=ROLES, default='operador')
    telefono = models.CharField(max_length=20, blank=True)
    departamento = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_rol_display()}"
    
    @property
    def es_admin(self):
        return self.rol == 'admin' or self.user.is_superuser
    
    @property
    def es_supervisor(self):
        return self.rol in ['admin', 'supervisor'] or self.user.is_superuser
    
    @property
    def puede_gestionar_usuarios(self):
        return self.rol in ['admin', 'rrhh'] or self.user.is_superuser
