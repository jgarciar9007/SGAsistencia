import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zkmanager.settings')
django.setup()

from empleados.models import Empleado
from dispositivos.models import Dispositivo, UsuarioDispositivo, AsistenciaCruda

def run():
    print("Simulating dashboard data...")
    
    # 1. Setup Device
    disp, _ = Dispositivo.objects.get_or_create(
        ip="192.168.1.99",
        defaults={"nombre": "Puerta Demo", "puerto": 4370, "activo": True}
    )
    
    # Helper to clean previous demo data for today to avoid duplicates
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def create_demo_user(name, surname, code, dni, hour=None, minute=None):
        # 1. Create Empleado
        emp, created = Empleado.objects.get_or_create(
            numero=code,
            defaults={
                "nombre": name,
                "apellido": surname,
                "doc_id": dni,
                "departamento": "Demo Dept",
                "puesto": "Staff",
                "dispositivo": disp,
                "user_id": code,
                "uid": int(code),
                "activo": True
            }
        )
        
        # 2. Create UsuarioDispositivo
        ud, _ = UsuarioDispositivo.objects.get_or_create(
            dispositivo=disp,
            user_id=code,
            defaults={
                "uid": int(code),
                "nombre": f"{name} {surname}",
                "empleado": emp,
                "activo": True
            }
        )
        
        # 3. Create Attendance (if time provided)
        if hour is not None:
            # Check if exists for today
            exists = AsistenciaCruda.objects.filter(
                usuario=ud,
                ts__gte=today_start
            ).exists()
            
            if not exists:
                mark_time = timezone.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                AsistenciaCruda.objects.create(
                    dispositivo=disp,
                    usuario=ud,
                    user_id=code,
                    uid=int(code),
                    ts=mark_time,
                    status=0, # Check-in
                    raw_status="0"
                )
                print(f"Marcaje creado para {name} a las {hour}:{minute}")
                
    # --- Scenario ---
    # 3 Puntuales (08:50 - 08:58)
    create_demo_user("Ana", "Puntual", "9001", "D9001", 8, 50)
    create_demo_user("Beto", "Temprano", "9002", "D9002", 8, 55)
    create_demo_user("Carla", "Hora", "9003", "D9003", 8, 58)
    
    # 2 Tardes (> 09:05)
    create_demo_user("Daniel", "Tarde", "9004", "D9004", 9, 15)
    create_demo_user("Elena", "Retraso", "9005", "D9005", 9, 30)
    
    # 3 Ausentes (No records)
    create_demo_user("Fabio", "Ausente", "9006", "D9006")
    create_demo_user("Gabriela", "Falta", "9007", "D9007")
    create_demo_user("Hugo", "Enfermo", "9008", "D9008")

    print("Datos simulados correctamente.")

if __name__ == "__main__":
    run()
