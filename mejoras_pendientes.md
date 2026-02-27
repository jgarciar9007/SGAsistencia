# Mejoras Pendientes y Deuda Técnica - SGAsistencia

Basado en la revisión del proyecto, la siguiente es una lista priorizada de mejoras pendientes para optimizar la mantenibilidad, escalabilidad y operabilidad del sistema. 

> [!IMPORTANT]
> **RECORDATORIO:** Cualquier actualización o mejora de base de datos no debe involucrar la pérdida de datos (`DropTable`, `Delete`). Las actualizaciones deben preservar el histórico existente en la BD PostgreSQL de producción (`192.168.20.3`).

### 1. Sistema y Despliegue (Alta Prioridad)
- [ ] **Migración a PostgreSQL en Local:** Cambiar de SQLite a PostgreSQL en los entornos de desarrollo/pruebas (`settings.py`) conectando al servidor `192.168.20.3` para homologar con el entorno de producción.
- [ ] **Automatización de Despliegue:** Crear un script de Bash (ej. `update.sh`) en servidor de producción (`192.168.20.7`) que automatice los siguientes pasos al momento de un pase a producción:
  - Hacer un volcado/backup rápido de la BD por seguridad.
  - Ejecutar `git pull` o traer los últimos cambios.
  - Actualizar dependencias (`pip install -r requirements.txt`).
  - Correr migraciones no destructivas (`python manage.py migrate`).
  - Recolectar estáticos (`python manage.py collectstatic --noinput`).
  - Reiniciar el servicio de Waitress.

### 2. Refactorización y Arquitectura (Media Prioridad)
- [ ] **Refactorizar `reportes/views.py`:** Separar la masiva lógica de generación de archivos PDF (implementada con `reportlab`) de los endpoints o controladores ("Views" de Django). Mover la lógica de dibujo a clases de servicio dentro de una nueva carpeta `reportes/services/pdf_generator.py`. Esto mejorará exponencialmente la legibilidad y el mantenimiento.
- [ ] **Limpiar Código Muerto (`usuarios` app):** La aplicación `usuarios` (la cual contiene el modelo `PerfilUsuario` y control de RBAC) y sus views/templates están actualmente desconectados del sistema (no configurado en `INSTALLED_APPS` ni `urls.py`). 
  - *Decisión requerida:* Eliminar la app por completo si se decidió no usar ese control de roles elaborado, o bien integrarla formalmente al proyecto si hace falta.
- [ ] **Buenas Prácticas de Importación:** Mover las importaciones locales de librerías en métodos al nivel superior del archivo respectivo. Por ejemplo, la importación de `Decimal` dentro del método de `save()` en el modelo `NominaEmpleado`.

### 3. Funcionalidades de Usuario (Baja Prioridad / Opcional)
- [ ] **Tareas en Segundo Plano (Sincronización Automática):** Implementar Celery & Redis (o comandos personalizados con Cron/APScheduler integrados a Django) para descargar de manera automática y periódica los datos de asistencia desde los equipos `ZKTeco`, reemplazando la dependencia exclusiva en la validación/descarga puramente manual del usuario.
