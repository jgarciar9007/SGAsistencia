from django.contrib import admin
from .models import NominaPeriodo, NominaEmpleado

class NominaEmpleadoInline(admin.TabularInline):
    model = NominaEmpleado
    extra = 0
    readonly_fields = ("neto_pagar",)
    can_delete = False
    
    fields = ("empleado", "salario_base", "dias_ausencia", "monto_descuento_ausencia", "bonos", "descuentos", "neto_pagar")

@admin.register(NominaPeriodo)
class NominaPeriodoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "inicio", "fin", "creado_en", "finalizado", "total_neto")
    list_filter = ("inicio", "fin", "finalizado")
    search_fields = ("nota",)
    date_hierarchy = "inicio"
    inlines = [NominaEmpleadoInline]
    
    def total_neto(self, obj):
        from django.db.models import Sum
        return obj.detalles.aggregate(total=Sum("neto_pagar"))["total"] or 0
    total_neto.short_description = "Total Pagar"

@admin.register(NominaEmpleado)
class NominaEmpleadoAdmin(admin.ModelAdmin):
    list_display = ("empleado", "periodo", "salario_base", "neto_pagar")
    list_filter = ("periodo", "empleado__departamento")
    search_fields = ("empleado__nombre", "empleado__apellido", "empleado__numero")
