from decimal import Decimal
from django.db import models
from empleados.models import Empleado

class NominaPeriodo(models.Model):
    """
    Representa un proceso de nómina para un rango de fechas.
    """
    inicio = models.DateField()
    fin = models.DateField()
    creado_en = models.DateTimeField(auto_now_add=True)
    finalizado = models.BooleanField(default=False)
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-inicio"]
        verbose_name = "Periodo de Nómina"
        verbose_name_plural = "Periodos de Nómina"

    def __str__(self):
        return f"Nómina {self.inicio} a {self.fin}"

class NominaEmpleado(models.Model):
    """
    Cálculo individual de nómina para un empleado en un periodo.
    """
    periodo = models.ForeignKey(NominaPeriodo, on_delete=models.CASCADE, related_name="detalles")
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT)
    
    salario_base = models.DecimalField(max_digits=12, decimal_places=2)
    dias_ausencia = models.IntegerField(default=0)
    monto_descuento_ausencia = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    bonos = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    otros_ingresos = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    descuentos = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    impuestos = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    neto_pagar = models.DecimalField(max_digits=12, decimal_places=2)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["periodo", "empleado"]

    def save(self, *args, **kwargs):
        # Asegurar que sean Decimal para evitar TypeErrors si vienen del form como str
        sb = Decimal(str(self.salario_base or 0))
        bo = Decimal(str(self.bonos or 0))
        oi = Decimal(str(self.otros_ingresos or 0))
        da = Decimal(str(self.monto_descuento_ausencia or 0))
        de = Decimal(str(self.descuentos or 0))
        im = Decimal(str(self.impuestos or 0))
        
        ingresos = sb + bo + oi
        egresos = da + de + im
        self.neto_pagar = ingresos - egresos
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.empleado} - {self.periodo}"
