from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.db import transaction
from .models import PerfilUsuario
from .forms import CrearUsuarioForm, EditarUsuarioForm, CambiarPasswordForm

def es_admin_o_rrhh(user):
    """Verifica si el usuario puede gestionar otros usuarios"""
    if user.is_superuser:
        return True
    if hasattr(user, 'perfil'):
        return user.perfil.puede_gestionar_usuarios
    return False

@login_required
@user_passes_test(es_admin_o_rrhh, login_url='/dashboard/')
def listar_usuarios(request):
    """Lista todos los usuarios del sistema"""
    usuarios = User.objects.select_related('perfil').all().order_by('-date_joined')
    return render(request, 'usuarios/listar.html', {
        'usuarios': usuarios
    })

@login_required
@user_passes_test(es_admin_o_rrhh, login_url='/dashboard/')
@transaction.atomic
def crear_usuario(request):
    """Crea un nuevo usuario con su perfil"""
    if request.method == 'POST':
        form = CrearUsuarioForm(request.POST)
        if form.is_valid():
            # Crear usuario
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_active=form.cleaned_data['activo']
            )
            
            # Crear perfil
            PerfilUsuario.objects.create(
                user=user,
                rol=form.cleaned_data['rol'],
                telefono=form.cleaned_data.get('telefono', ''),
                departamento=form.cleaned_data.get('departamento', ''),
                activo=form.cleaned_data['activo']
            )
            
            messages.success(request, f'Usuario {user.username} creado exitosamente.')
            return redirect('usuarios:listar')
    else:
        form = CrearUsuarioForm()
    
    return render(request, 'usuarios/crear.html', {'form': form})

@login_required
@user_passes_test(es_admin_o_rrhh, login_url='/dashboard/')
@transaction.atomic
def editar_usuario(request, user_id):
    """Edita un usuario existente"""
    usuario = get_object_or_404(User, pk=user_id)
    
    # Crear perfil si no existe
    if not hasattr(usuario, 'perfil'):
        PerfilUsuario.objects.create(user=usuario)
    
    if request.method == 'POST':
        form = EditarUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            # Actualizar usuario
            usuario.email = form.cleaned_data['email']
            usuario.first_name = form.cleaned_data['first_name']
            usuario.last_name = form.cleaned_data['last_name']
            usuario.is_active = form.cleaned_data['activo']
            usuario.save()
            
            # Actualizar perfil
            usuario.perfil.rol = form.cleaned_data['rol']
            usuario.perfil.telefono = form.cleaned_data.get('telefono', '')
            usuario.perfil.departamento = form.cleaned_data.get('departamento', '')
            usuario.perfil.activo = form.cleaned_data['activo']
            usuario.perfil.save()
            
            messages.success(request, f'Usuario {usuario.username} actualizado exitosamente.')
            return redirect('usuarios:listar')
    else:
        initial_data = {
            'email': usuario.email,
            'first_name': usuario.first_name,
            'last_name': usuario.last_name,
            'rol': usuario.perfil.rol,
            'telefono': usuario.perfil.telefono,
            'departamento': usuario.perfil.departamento,
            'activo': usuario.is_active,
        }
        form = EditarUsuarioForm(initial=initial_data)
    
    return render(request, 'usuarios/editar.html', {
        'form': form,
        'usuario': usuario
    })

@login_required
def cambiar_password(request):
    """Permite al usuario cambiar su propia contraseña"""
    if request.method == 'POST':
        form = CambiarPasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Mantener sesión activa
            messages.success(request, 'Tu contraseña ha sido cambiada exitosamente.')
            return redirect('dashboard')
    else:
        form = CambiarPasswordForm(request.user)
    
    return render(request, 'usuarios/cambiar_password.html', {'form': form})

@login_required
@user_passes_test(es_admin_o_rrhh, login_url='/dashboard/')
def resetear_password(request, user_id):
    """Permite a admin/RRHH resetear la contraseña de un usuario"""
    usuario = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        nueva_password = request.POST.get('nueva_password')
        if nueva_password:
            usuario.set_password(nueva_password)
            usuario.save()
            messages.success(request, f'Contraseña de {usuario.username} reseteada exitosamente.')
            return redirect('usuarios:listar')
    
    return render(request, 'usuarios/resetear_password.html', {'usuario': usuario})

@login_required
@user_passes_test(es_admin_o_rrhh, login_url='/dashboard/')
def eliminar_usuario(request, user_id):
    """Desactiva un usuario (no lo elimina físicamente)"""
    usuario = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        usuario.is_active = False
        usuario.save()
        if hasattr(usuario, 'perfil'):
            usuario.perfil.activo = False
            usuario.perfil.save()
        messages.success(request, f'Usuario {usuario.username} desactivado exitosamente.')
        return redirect('usuarios:listar')
    
    return render(request, 'usuarios/eliminar.html', {'usuario': usuario})
