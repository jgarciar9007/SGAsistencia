from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from usuarios.models import PerfilUsuario

class Command(BaseCommand):
    help = 'Inicializa el usuario administrador con contraseña predeterminada'

    def handle(self, *args, **options):
        username = 'admin'
        password = 'Cndes2026*'
        email = 'admin@cndes.com'
        
        # Verificar si el usuario ya existe
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            # Actualizar contraseña
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            
            # Asegurar que tenga perfil de admin
            if hasattr(user, 'perfil'):
                user.perfil.rol = 'admin'
                user.perfil.activo = True
                user.perfil.save()
            else:
                PerfilUsuario.objects.create(
                    user=user,
                    rol='admin',
                    activo=True
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Usuario "{username}" actualizado exitosamente con contraseña predeterminada'
                )
            )
        else:
            # Crear nuevo usuario admin
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name='Administrador',
                last_name='del Sistema'
            )
            
            # Crear perfil
            PerfilUsuario.objects.create(
                user=user,
                rol='admin',
                activo=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Usuario administrador "{username}" creado exitosamente'
                )
            )
        
        self.stdout.write(
            self.style.WARNING(
                f'\n📋 Credenciales de acceso:'
            )
        )
        self.stdout.write(f'   Usuario: {username}')
        self.stdout.write(f'   Contraseña: {password}')
        self.stdout.write(
            self.style.WARNING(
                f'\n⚠️  IMPORTANTE: Cambia esta contraseña después del primer inicio de sesión'
            )
        )
