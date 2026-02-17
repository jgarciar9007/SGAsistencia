
import os
import django
from django.db.models import Count

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zkmanager.settings")
django.setup()

from dispositivos.models import UsuarioDispositivo
from empleados.models import Empleado

def check_collisions():
    print("--- Checking for ID Collisions ---")
    
    # 1. Check for duplicates in UsuarioDispositivo (same user_id on different devices/persons?)
    # Actually, we want to know if the SAME user_id is used by DIFFERENT people.
    # Logic: Group by user_id. If count > 1, check if they map to different Empleados.
    
    dupes = UsuarioDispositivo.objects.values('user_id').annotate(count=Count('user_id')).filter(count__gt=1)
    
    found_issues = False
    
    for d in dupes:
        uid = d['user_id']
        # Get all records with this user_id
        records = UsuarioDispositivo.objects.filter(user_id=uid)
        
        # Check if they belong to different employees
        emp_ids = set(records.values_list('empleado_id', flat=True))
        
        if len(emp_ids) > 1:
            print(f"[!] COLLISION: User ID '{uid}' is associated with multiple entities: {emp_ids}")
            for r in records:
                emp_name = r.empleado.nombre_completo if r.empleado else "None"
                print(f"    - Dev: {r.dispositivo.nombre}, Emp: {emp_name} (ID: {r.empleado_id})")
            found_issues = True
        elif None in emp_ids and len(emp_ids) > 1:
             # Mix of None and some Employee ID is okay-ish (maybe same person not linked on one device)
             # But if we have duplicates in Empleado table too...
             pass

    # 2. Check collisions between Empleado.user_id
    emp_dupes = Empleado.objects.values('user_id').annotate(count=Count('id')).filter(count__gt=1).exclude(user_id="")
    if emp_dupes.exists():
        print(f"[!] Empleado Table Duplicates: {list(emp_dupes)}")
        found_issues = True

    if not found_issues:
        print("No critical ID collisions found.")
    else:
        print("Issues found.")

if __name__ == "__main__":
    check_collisions()
