
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zkmanager.settings")
django.setup()

from empleados.views import _siguiente_user_id
from dispositivos.models import UsuarioDispositivo, Dispositivo
from empleados.models import Empleado

def test_id_generation():
    print("--- Testing ID Generation ---")
    
    # 1. Get next ID
    next_id = _siguiente_user_id()
    print(f"Next available ID: {next_id}")
    
    # 2. Simulate ID usage
    # If next_id is '200', let's say we have '200' used in Empleados but not devices
    # We can't easily create dummy data without messing up DB, so we just check logic.
    
    # Let's perform a dry run matching the logic
    used_ids = set(UsuarioDispositivo.objects.values_list('user_id', flat=True))
    used_ids.update(Empleado.objects.exclude(user_id="").values_list('user_id', flat=True))
    
    print(f"Used IDs in DB: {sorted(list(used_ids))}")
    
    if next_id in used_ids:
        print("[!] FAIL: Generated ID is already in use!")
    else:
        print("[OK] Generated ID is unique.")
        
    # Check strict sequence
    base = 200
    while str(base) in used_ids:
        base += 10
        
    if str(base) == next_id:
        print(f"[OK] ID {next_id} is the correct next sequence number.")
    else:
        print(f"[!] FAIL: Expected {base}, got {next_id}")

if __name__ == "__main__":
    test_id_generation()
