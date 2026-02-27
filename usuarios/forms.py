from django import forms
from django.contrib.auth.models import User, Group

class UserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirmar Contraseña")
    
    # Simple selection for roles (Staff or Admin, mapping to Django groups or just is_staff flag)
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all(), 
        required=False, 
        label="Rol de Usuario",
        empty_label="--- Seleccione un Rol ---"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico',
            'is_active': 'Activo'
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            self.add_error('confirm_password', "Las contraseñas no coinciden.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            grupo = self.cleaned_data.get('grupo')
            if grupo:
                user.groups.add(grupo)
        return user


class UserUpdateForm(forms.ModelForm):
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all(), 
        required=False, 
        label="Rol de Usuario",
        empty_label="--- Seleccione un Rol ---"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico',
            'is_active': 'Activo'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            grupo_actual = self.instance.groups.first()
            if grupo_actual:
                self.initial['grupo'] = grupo_actual

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            user.groups.clear()
            grupo = self.cleaned_data.get('grupo')
            if grupo:
                user.groups.add(grupo)
        return user
