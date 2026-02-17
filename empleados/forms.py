from django import forms
from .models import Empleado, Candidato, Documento, BajaAutorizada
from dispositivos.models import UsuarioDispositivo, Dispositivo

# ... (EmpleadoForm remains)

class LinkUsuarioDispositivoForm(forms.Form):
    dispositivo = forms.ModelChoiceField(
        queryset=Dispositivo.objects.all(),
        label="Dispositivo",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_dispositivo"})
    )
    usuario = forms.ModelChoiceField(
        queryset=UsuarioDispositivo.objects.none(),
        label="Usuario en el Dispositivo",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_usuario"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si hay datos POST, filtrar el queryset de usuario
        if 'dispositivo' in self.data:
            try:
                dispositivo_id = int(self.data.get('dispositivo'))
                self.fields['usuario'].queryset = UsuarioDispositivo.objects.filter(dispositivo_id=dispositivo_id).order_by('nombre', 'user_id')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty queryset
        # Opcional: si queremos precargar algo

class EmpleadoForm(forms.ModelForm):
    crear_en_dispositivo = forms.BooleanField(
        required=False,
        initial=False,
        label="Crear también en el equipo biométrico (si tiene dispositivo asignado)"
    )

    class Meta:
        model = Empleado
        fields = [
            "numero", "nombre", "apellido", "doc_id", "foto",
            "telefono", "email", "direccion",
            "departamento", "area", "seccion",
            "tipo_vinculacion", "puesto", "salario_base",
            "dispositivo", "user_id", "uid", 
            "activo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apellido": forms.TextInput(attrs={"class": "form-control"}),
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "doc_id": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "departamento": forms.TextInput(attrs={"class": "form-control"}),
            "area": forms.TextInput(attrs={"class": "form-control"}),
            "seccion": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_vinculacion": forms.Select(attrs={"class": "form-select"}),
            "puesto": forms.TextInput(attrs={"class": "form-control"}),
            "dispositivo": forms.Select(attrs={"class": "form-select"}),
            "user_id": forms.TextInput(attrs={"class": "form-control"}),
            "uid": forms.NumberInput(attrs={"class": "form-control"}),
            "foto": forms.FileInput(attrs={"class": "form-control"}),
            "salario_base": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def clean_numero(self):
        return (self.cleaned_data.get("numero") or "").strip()


class VincularUsuarioForm(forms.Form):
    usuario = forms.ModelChoiceField(
        queryset=UsuarioDispositivo.objects.none(),
        label="Seleccione usuario del equipo",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    def __init__(self, *args, **kwargs):
        self.empleado = kwargs.pop("empleado", None)
        super().__init__(*args, **kwargs)
        if self.empleado:
            qs = UsuarioDispositivo.objects.all().order_by("dispositivo__nombre", "nombre", "user_id")
            self.fields["usuario"].queryset = qs
            self.fields["usuario"].label_from_instance = lambda obj: f"{obj.dispositivo.nombre} - {obj.nombre} (ID: {obj.user_id})"


class CandidatoForm(forms.ModelForm):
    class Meta:
        model = Candidato
        fields = [
            "nombre", "apellido", "doc_id",
            "telefono", "email",
            "skills", "titulaciones",
            "estado", "nota"
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apellido": forms.TextInput(attrs={"class": "form-control"}),
            "doc_id": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "skills": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "titulaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "nota": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "descripcion", "archivo"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control"}),
            "archivo": forms.FileInput(attrs={"class": "form-control"}),
        }


class BajaAutorizadaForm(forms.ModelForm):
    class Meta:
        model = BajaAutorizada
        fields = ["fecha_inicio", "fecha_fin", "tipo", "descripcion"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control"}),
        }
