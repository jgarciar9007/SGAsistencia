from django.db import models


class Dispositivo(models.Model):
    PROTOCOLOS = [('tcp', 'TCP'), ('udp', 'UDP')]
    nombre = models.CharField(max_length=80)
    ip = models.GenericIPAddressField(protocol='both', unpack_ipv4=True)
    puerto = models.PositiveIntegerField(default=4370)
    protocolo = models.CharField(max_length=3, choices=PROTOCOLOS, default='tcp')
    password = models.CharField(max_length=64, blank=True)
    timeout = models.PositiveIntegerField(default=5)
    omitir_ping = models.BooleanField(default=False)
    max_size_tcp = models.PositiveIntegerField(default=1024)
    max_size_udp = models.PositiveIntegerField(default=1024)
    tz = models.CharField(max_length=50, default='Africa/Malabo')
    ubicacion = models.CharField(max_length=120, blank=True)
    activo = models.BooleanField(default=True)
    ultimo_descarga = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['ip', 'puerto'], name='uq_ip_puerto')
        ]

    def __str__(self):
        return f"{self.nombre} ({self.ip}:{self.puerto}/{self.protocolo})"


class UsuarioDispositivo(models.Model):
    dispositivo = models.ForeignKey(Dispositivo, on_delete=models.CASCADE, related_name='usuarios')
    uid = models.PositiveIntegerField(null=True, blank=True, help_text="UID interno, puede ser nulo")
    user_id = models.CharField(max_length=32, blank=True, default="", help_text="ID mostrado en el equipo")
    nombre = models.CharField(max_length=64, blank=True, default="")
    privilegio = models.IntegerField(null=True, blank=True)
    grupo_id = models.IntegerField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    # 🔗 Enlace con el empleado
    empleado = models.ForeignKey(
        "empleados.Empleado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios_dispositivo"
    )

    class Meta:
        ordering = ['dispositivo', 'user_id', 'uid']
        unique_together = (
            ('dispositivo', 'user_id'),
            ('dispositivo', 'uid'),
        )

    def __str__(self):
        return f"{self.nombre or self.user_id or self.uid}"


class AsistenciaCruda(models.Model):
    dispositivo = models.ForeignKey(Dispositivo, on_delete=models.CASCADE, related_name='marcajes')
    usuario = models.ForeignKey(UsuarioDispositivo, null=True, blank=True, on_delete=models.SET_NULL, related_name='marcajes')
    user_id = models.CharField(max_length=32)
    uid = models.PositiveIntegerField(null=True, blank=True)
    ts = models.DateTimeField()
    status = models.SmallIntegerField()
    punch = models.SmallIntegerField(null=True, blank=True)
    raw_status = models.CharField(max_length=16, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ts']
        indexes = [
            models.Index(fields=['ts']),
            models.Index(fields=['dispositivo', 'user_id']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['dispositivo', 'user_id', 'ts', 'status'], name='uq_marcaje_unico')
        ]

    def __str__(self):
        return f"{self.dispositivo.nombre} · {self.user_id} · {self.ts.isoformat()} · {self.status}"
