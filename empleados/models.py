from django.db import models
from django.db.models import Index

class Candidato(models.Model):
    """
    Personas en la 'Cantera' que aún no son empleados.
    """
    ESTADOS = [
        ("DISP", "Disponible"),
        ("PROC", "En Proceso"),
        ("DESC", "Descartado"),
        ("CONTR", "Contratado"), # Estado final cuando pasa a ser Empleado
    ]

    nombre = models.CharField(max_length=60)
    apellido = models.CharField(max_length=60)
    doc_id = models.CharField(max_length=30, unique=True, help_text="Documento de identidad")
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    skills = models.TextField(blank=True, help_text="Habilidades técnicas o blandas")
    titulaciones = models.TextField(blank=True, help_text="Títulos y certificaciones")
    
    estado = models.CharField(max_length=5, choices=ESTADOS, default="DISP")
    nota = models.TextField(blank=True, help_text="Notas internas sobre el candidato")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["apellido", "nombre"]
        indexes = [
            Index(fields=["doc_id"]),
            Index(fields=["apellido"]),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.get_estado_display()})"
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()


class Empleado(models.Model):
    TIPO_VINCULACION = [
        ("FUNC", "Funcionario"),
        ("PRAC", "Practicante"),
        ("CONT", "Contratado"),
    ]

    numero = models.CharField(max_length=20, unique=True, help_text="Código interno o número de nómina")
    nombre = models.CharField(max_length=60)
    apellido = models.CharField(max_length=60)
    doc_id = models.CharField(max_length=30, unique=True, help_text="Documento de identidad")
    
    # Nuevo campo de foto
    foto = models.ImageField(upload_to="empleados/fotos/", null=True, blank=True)

    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=120, blank=True)
    
    departamento = models.CharField(max_length=80, blank=True)
    area = models.CharField(max_length=80, blank=True)
    seccion = models.CharField(max_length=80, blank=True)

    tipo_vinculacion = models.CharField(
        max_length=5,
        choices=TIPO_VINCULACION,
        default="FUNC",
        help_text="Tipo de relación laboral"
    )
    puesto = models.CharField(max_length=100, blank=True, help_text="Cargo o puesto laboral")

    dispositivo = models.ForeignKey(
        "dispositivos.Dispositivo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empleados"
    )
    user_id = models.CharField(max_length=32, blank=True, help_text="ID en el sistema biométrico")
    uid = models.PositiveIntegerField(null=True, blank=True, help_text="UID interno del equipo")

    activo = models.BooleanField(default=True)
    
    # Nuevo campo para Nómina
    salario_base = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Salario base mensual")
    
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["apellido", "nombre"]
        indexes = [
            Index(fields=["numero"]),
            Index(fields=["doc_id"]),
            Index(fields=["departamento", "area"]),
            Index(fields=["dispositivo", "user_id"]),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.numero})"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()


class Documento(models.Model):
    """
    Archivos adjuntos (expediente digital).
    Puede pertenecer a un Empleado O a un Candidato.
    """
    TIPOS = [
        ("CV", "Curriculum Vitae"),
        ("ID", "Documento Identidad"),
        ("TIT", "Título / Certificación"),
        ("CON", "Contrato"),
        ("EXP", "Expediente General"),
        ("OTRO", "Otro"),
    ]

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="documentos", null=True, blank=True)
    candidato = models.ForeignKey(Candidato, on_delete=models.CASCADE, related_name="documentos", null=True, blank=True)
    
    tipo = models.CharField(max_length=5, choices=TIPOS, default="OTRO")
    descripcion = models.CharField(max_length=150, blank=True, help_text="Descripción breve del archivo")
    archivo = models.FileField(upload_to="documentos/%Y/%m/")
    
    subido_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descripcion or 'Sin descripción'}"


class BajaAutorizada(models.Model):
    """
    Control de ausencias justificadas o autorizadas (vacaciones, enfermedad, etc.)
    """
    TIPOS = [
        ("VACA", "Vacaciones"),
        ("ENFE", "Enfermedad / Médica"),
        ("PERM", "Permiso Personal"),
        ("OTRO", "Otro"),
    ]

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="bajas_autorizadas")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo = models.CharField(max_length=5, choices=TIPOS, default="OTRO")
    descripcion = models.CharField(max_length=200, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name = "Baja Autorizada"
        verbose_name_plural = "Bajas Autorizadas"

    def __str__(self):
        return f"{self.empleado} | {self.fecha_inicio} al {self.fecha_fin} ({self.get_tipo_display()})"
