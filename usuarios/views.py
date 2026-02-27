from django.shortcuts import render, redirect
from django.contrib.auth.models import User, Group
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import UserCreationForm, UserUpdateForm
from reportes.views import StaffOnlyMixin

# Decorador/Mixin para que solo los superusuarios o staff manejen usuarios
class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_superuser or self.request.user.is_staff)

class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "usuarios/usuario_list.html"
    context_object_name = "usuarios"
    paginate_by = 20

    def get_queryset(self):
        return User.objects.all().order_by('-is_active', 'username')

class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:lista")

    def form_valid(self, form):
        messages.success(self.request, "Usuario creado exitosamente.")
        return super().form_valid(form)

class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:lista")

    def form_valid(self, form):
        messages.success(self.request, "Usuario actualizado exitosamente.")
        return super().form_valid(form)

class UserDeleteView(AdminRequiredMixin, DeleteView):
    model = User
    template_name = "usuarios/usuario_confirm_delete.html"
    success_url = reverse_lazy("usuarios:lista")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Usuario eliminado correctamente.")
        return super().delete(request, *args, **kwargs)

class PasswordChangeCustomView(LoginRequiredMixin, PasswordChangeView):
    template_name = "usuarios/change_password.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Tu contraseña ha sido cambiada de forma exitosa.")
        return super().form_valid(form)
