import os
import django
import random
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zkmanager.settings')
django.setup()

from empleados.models import Candidato

def run():
    print("Populating Candidates (Cantera)...")
    
    candidates_data = [
        {
            "nombre": "Sofia", "apellido": "Marta", "doc_id": "C001", 
            "email": "sofia@example.com", "telefono": "222-111-001",
            "skills": "Python, Django, React", "titulaciones": "Ingeniera Software",
            "estado": "DISP", "nota": "Disponibilidad inmediata"
        },
        {
            "nombre": "Luis", "apellido": "Obiang", "doc_id": "C002", 
            "email": "luis@example.com", "telefono": "222-111-002",
            "skills": "Contabilidad, Excel", "titulaciones": "Licenciado en Economía",
            "estado": "PROC", "nota": "Entrevista técnica pendiente"
        },
        {
            "nombre": "Marta", "apellido": "Esono", "doc_id": "C003", 
            "email": "marta@example.com", "telefono": "222-111-003",
            "skills": "Gestión de RRHH, Leyes laborales", "titulaciones": "Abogada",
            "estado": "DESC", "nota": "No encaja salario"
        },
        {
            "nombre": "Pedro", "apellido": "Nguema", "doc_id": "C004", 
            "email": "pedro@example.com", "telefono": "222-111-004",
            "skills": "Seguridad, Chofer", "titulaciones": "Permiso B, C",
            "estado": "DISP", "nota": "Recomendado por Juan"
        },
        {
            "nombre": "Elena", "apellido": "Nchama", "doc_id": "C005", 
            "email": "elena@example.com", "telefono": "222-111-005",
            "skills": "Limpieza, Orden", "titulaciones": "Bachillerato",
            "estado": "PROC", "nota": "Evaluando referencias"
        },
        {
            "nombre": "Jose", "apellido": "Sima", "doc_id": "C006", 
            "email": "jose@example.com", "telefono": "222-111-006",
            "skills": "Carpintería, Mantenimiento", "titulaciones": "FP Mantenimiento",
            "estado": "DISP", "nota": ""
        }
    ]

    count = 0
    for c in candidates_data:
        obj, created = Candidato.objects.get_or_create(
            doc_id=c["doc_id"],
            defaults=c
        )
        if created:
            print(f"Created: {obj}")
            count += 1
        else:
            print(f"Skipped (exists): {obj}")

    print(f"Done. Created {count} candidates.")

if __name__ == "__main__":
    run()
