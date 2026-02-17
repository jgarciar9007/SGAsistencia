from django.contrib import admin
from .models import Dispositivo, UsuarioDispositivo, AsistenciaCruda


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ip', 'puerto', 'protocolo', 'ubicacion', 'activo')
    list_filter = ('protocolo', 'activo', 'ubicacion')
    search_fields = ('nombre', 'ip', 'ubicacion')


@admin.register(UsuarioDispositivo)
class UsuarioDispositivoAdmin(admin.ModelAdmin):
    list_display = ('dispositivo', 'uid', 'user_id', 'nombre', 'privilegio', 'activo')
    list_filter = ('dispositivo', 'activo', 'privilegio')
    search_fields = ('user_id', 'nombre')


@admin.register(AsistenciaCruda)
class AsistenciaCrudaAdmin(admin.ModelAdmin):
    list_display = ('ts', 'dispositivo', 'user_id', 'status', 'punch')
    list_filter = ('dispositivo', 'status')
    search_fields = ('user_id',)
    date_hierarchy = 'ts'
    actions = ['delete_by_date_range']

    def delete_by_date_range(self, request, queryset):
        from django.shortcuts import render
        from django.contrib import messages
        from django.utils.translation import gettext as _
        
        if 'apply' in request.POST:
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            if start_date and end_date:
                # Filter by range (inclusive)
                deleted_count, _ = AsistenciaCruda.objects.filter(
                    ts__date__range=[start_date, end_date]
                ).delete()
                
                self.message_user(request, 
                                  _(f"Se eliminaron {deleted_count} registros de asistencia entre {start_date} y {end_date}."), 
                                  messages.SUCCESS)
                return None # Return None to redirect back to changelist
            else:
                 self.message_user(request, _("Por favor ingrese fecha de inicio y fin."), messages.ERROR)
        
        return render(request, 'admin/dispositivos/asistenciacruda/delete_by_date_range.html', context={
            'queryset': queryset,
            'opts': self.model._meta,
        })
    
    delete_by_date_range.short_description = "Eliminar registros por rango de fechas"
