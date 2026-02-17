from django import forms
from .models import Dispositivo

class DispositivoForm(forms.ModelForm):
    """
    Formulario con validaciones básicas para parámetros del equipo.
    """
    class Meta:
        model = Dispositivo
        fields = [
            'nombre','ip','puerto','protocolo','password','timeout',
            'omitir_ping','max_size_tcp','max_size_udp','tz','ubicacion','activo'
        ]

    def clean_puerto(self):
        p = self.cleaned_data['puerto']
        if not (1 <= p <= 65535):
            raise forms.ValidationError("Puerto inválido")
        return p

    def clean_timeout(self):
        t = self.cleaned_data['timeout']
        if t == 0 or t > 60:
            raise forms.ValidationError("Timeout entre 1 y 60 segundos")
        return t
