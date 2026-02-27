#!/bin/bash

# Script de actualización para SGAsistencia (ZkManager)
# Uso: Ejecutar desde la raíz del proyecto en el servidor 192.168.20.7

echo "=============================================="
echo " Iniciando actualización de SGAsistencia..."
echo "=============================================="

# 1. Copia de seguridad de la base de datos (PostgreSQL remota)
# Usamos las credenciales de la DB de producción predeterminadas. 
# NOTA: Asegúrate de tener pg_dump instalado en el servidor web, o si PGPASSWORD está en el entorno local.
echo "[1/5] Realizando copia de seguridad de la BD..."
export PGPASSWORD="Cndes2026*"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/var/backups/sgasistencia"

# Crear directorio temporal si no existe
mkdir -p $BACKUP_DIR
pg_dump -h 192.168.20.3 -U postgres -d asistencia -F c -f $BACKUP_DIR/asistencia_$TIMESTAMP.dump
if [ $? -eq 0 ]; then
    echo "  -> Backup creado: $BACKUP_DIR/asistencia_$TIMESTAMP.dump"
else
    echo "  -> ADVERTENCIA: Falló el backup de la base de datos."
fi

# 2. Bajar los últimos cambios de Git
echo "[2/5] Descargando últimos cambios (Git Pull)..."
git pull origin main

# 3. Instalar dependencias actualizadas
echo "[3/5] Actualizando dependencias..."
source venv/bin/activate 2>/dev/null || . venv/bin/activate 2>/dev/null || echo "No se encontró venv. Asumiendo entorno global o docker..."
pip install -r requirements.txt

# 4. Ejecutar migraciones
# IMPORTANTE: Nunca borrar tablas ni datos críticos
echo "[4/5] Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

# 5. Recolectar estáticos
echo "[5/5] Actualizando archivos estáticos..."
python manage.py collectstatic --noinput

# 6. Reiniciar el servicio (Waitress)
echo "[6/5] Reiniciando servicio web..."
# Esto asume que el proceso se maneja con systemd, supervisor o pm2. 
# Modificar el comando según el sistema de init que use el servidor.
# Ejemplo asumiendo un servicio systemd llamado sgasistencia.service:
# systemctl restart sgasistencia

echo "=============================================="
echo " Actualización completada exitosamente. "
echo "=============================================="
