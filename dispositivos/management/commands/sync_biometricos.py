import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from dispositivos.models import Dispositivo
from dispositivos.views import _conn_with_fallbacks, descargar_usuarios, descargar_asistencia
from zk import ZK
from django.db import transaction

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sincroniza usuarios y registros de asistencia para todos los dispositivos activos.'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando tarea de sincronización automática de biométricos...")
        dispositivos_activos = Dispositivo.objects.filter(activo=True)

        if not dispositivos_activos.exists():
            self.stdout.write(self.style.WARNING("No hay dispositivos activos configurados."))
            return

        total_descargados = 0
        total_errores = 0

        for dispositivo in dispositivos_activos:
            self.stdout.write(f"--- Procesando dispositivo: {dispositivo.nombre} ({dispositivo.ip}) ---")
            
            try:
                # 1. Probar la conexión primero
                conn, pwd_usada = _conn_with_fallbacks(dispositivo)
                if not conn:
                    self.stdout.write(self.style.ERROR(f"Error de conexión con {dispositivo.nombre}. Saltando."))
                    total_errores += 1
                    continue
                
                # 2. Descargar Usuarios (Opcional, pero recomendado para mantener consistencia)
                # Al ser un script de fondo, replicaremos parte de la lógica de views.py aquí
                # para no depender de objetos 'request' simulados.
                self._sincronizar_usuarios_y_registros(conn, dispositivo)
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error inesperado procesando {dispositivo.nombre}: {e}"))
                logger.exception(f"Error sincronizando dispositivo {dispositivo.nombre}")
                total_errores += 1
            else:
                self.stdout.write(self.style.SUCCESS(f"Sincronización completa para {dispositivo.nombre}."))
                total_descargados += 1

        self.stdout.write("===============================================")
        self.stdout.write(self.style.SUCCESS(f"Resumen: {total_descargados} dispositivos exitosos, {total_errores} con errores."))

    def _sincronizar_usuarios_y_registros(self, conn, dispositivo):
        """
        Extrae la lógica de comunicación con ZK para sincronizar 
        usuarios y sus registros de asistencia.
        """
        from dispositivos.models import UsuarioDispositivo, AsistenciaCruda
        from empleados.models import Empleado
        from pyzk.zk import const
        
        try:
            # Deshabilitar dispositivo temporalmente mientras leemos
            try:
                conn.disable_device()
            except Exception:
                pass
                
            # 1. Usuarios
            self.stdout.write("    Descargando usuarios...")
            zk_users = conn.get_users()
            nuevos = 0
            actualizados = 0
            
            # Formateadores (similares a views.py)
            def _to_int(v): return int(v) if str(v).isdigit() else None
            def _to_str(v, mx=32): return str(v or "")[:mx]

            for u in zk_users:
                # pyzk normalmente devuelve objetos con atributos definidos o dicts
                # Algunos pyzk tienen u.uid, u.user_id, etc.
                uid_val = getattr(u, "uid", None) or u.get("uid") if isinstance(u, dict) else _to_int(getattr(u, "uid", ""))
                user_id_val = getattr(u, "user_id", None) or u.get("user_id") if isinstance(u, dict) else _to_str(getattr(u, "user_id", ""))
                
                if not user_id_val: 
                    continue
                    
                nombre_val = getattr(u, "name", None) or u.get("name") if isinstance(u, dict) else getattr(u, "name", "")
                priv_val = getattr(u, "privilege", None) or u.get("privilege") if isinstance(u, dict) else _to_int(getattr(u, "privilege", 0))

                ud, created = UsuarioDispositivo.objects.get_or_create(
                    dispositivo=dispositivo,
                    user_id=str(user_id_val),
                    defaults={
                        'uid': uid_val,
                        'nombre': str(nombre_val or "")[:64],
                        'privilegio': priv_val,
                    }
                )
                if created:
                    nuevos += 1
                    # Auto-vincular si existe un Empleado con ese doc_id o numero que coincida en user_id
                    emp = Empleado.objects.filter(doc_id=user_id_val, activo=True).first()
                    if emp:
                        ud.empleado = emp
                        ud.save()
                else:
                    actualizados += 1
            
            self.stdout.write(f"    Usuarios: {nuevos} nuevos, {actualizados} actualizados/existentes.")

            # 2. Asistencia
            self.stdout.write("    Descargando registros de asistencia...")
            try:
                registros = conn.get_attendance()
            except Exception as e:
                # Algunos terminales (ej: MA04) no devuelven listas clásicas o fallan en empty
                if "No attendances" in str(e):
                    registros = []
                else:
                    raise e
                    
            marcajes_nuevos = 0
            
            # Bulk create list
            asist_to_create = []
            existentes_query = set(AsistenciaCruda.objects.filter(dispositivo=dispositivo).values_list('user_id', 'ts', 'status'))
            
            for att in registros:
                # att es un objeto de pyzk Attendance
                att_uid = str(getattr(att, "user_id", ""))
                att_ts = getattr(att, "timestamp", None)
                att_status = getattr(att, "status", 0)
                att_punch = getattr(att, "punch", 0)
                
                if not att_uid or not att_ts:
                    continue
                    
                # Convertir a timezone aware para guardar en DB
                if timezone.is_naive(att_ts):
                    att_ts = timezone.make_aware(att_ts, timezone.get_current_timezone())
                    
                key_eval = (att_uid, att_ts, att_status)
                if key_eval not in existentes_query:
                    # Encontrar el UD asociado
                    ud_asoc = UsuarioDispositivo.objects.filter(dispositivo=dispositivo, user_id=att_uid).first()
                    
                    asist_to_create.append(AsistenciaCruda(
                        dispositivo=dispositivo,
                        usuario=ud_asoc,
                        user_id=att_uid,
                        ts=att_ts,
                        status=att_status,
                        punch=att_punch,
                    ))
                    existentes_query.add(key_eval)
                    
            if asist_to_create:
                # Hacer bulk create ignorando conflictos por si acaso
                AsistenciaCruda.objects.bulk_create(asist_to_create, ignore_conflicts=True)
                marcajes_nuevos = len(asist_to_create)

            # Actualizar dispositivo
            dispositivo.ultimo_descarga = timezone.now()
            dispositivo.save(update_fields=['ultimo_descarga'])
            
            self.stdout.write(f"    Marcajes: {marcajes_nuevos} registros integrados en la base de datos.")

        finally:
            try:
                conn.enable_device()
            except Exception:
                pass
            try:
                conn.disconnect()
            except Exception:
                pass
