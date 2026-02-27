# Plan de Mantenimiento y Actualización: SGAsistencia

Este documento sirve como hoja de ruta para el mantenimiento, despliegue y desarrollo continuo de la plataforma SGAsistencia (zkmanager).

## 1. Datos de Producción (Entorno Actual)

**Servidor de Aplicación (Host Público):**
*   **IP:** `192.168.20.7`
*   **Usuario SSH:** `root`
*   **Contraseña:** `Cndes2026*`

**Base de Datos (Producción):**
*   **Motor:** PostgreSQL
*   **IP:** `192.168.20.3`
*   **Nombre de DB:** `asistencia`
*   **Usuario:** `postgres`
*   **Contraseña:** `Cndes2026*`

> [!CAUTION]
> **REGLA DE ORO PARA ACTUALIZACIONES:** Nunca se puede borrar información de la base de datos de producción. Cualquier migración o actualización de modelos debe limitarse a **agregar nuevos campos**, **modificar estructuras existentes sin pérdida de datos** o corregir tipos de datos. Evitar a toda costa `DropTable` u operaciones destructivas para preservar el histórico de asistencias y nóminas.

---

## 2. Resumen de Funcionalidades Actuales (Core)

La plataforma actualmente soporta los siguientes módulos y capacidades:

### 2.1 Módulo de Dispositivos Biométricos
*   Gestión (CRUD) de dispositivos IP (ZKTeco).
*   Prueba de conexión (Ping / SDK).
*   Sincronización manual: Descarga de usuarios y huellas desde el equipo hacia el sistema.
*   Sincronización manual: Descarga de registros de asistencia crudos (`AsistenciaCruda`).
*   Listado y exportación CSV de marcajes y usuarios del dispositivo.

### 2.2 Módulo de RRHH (Empleados y Cantera)
*   **Empleados:** CRUD de empleados, incluyendo datos de contacto, departamento, área, salario base y vinculación (Funcionario, Contratado, Practicante).
*   **Cantera (Candidatos):** Gestión de posibles empleados (estado Disponible, En Proceso, etc.). Posibilidad de promover un candidato a empleado.
*   **Documentación Digital:** Subida de archivos PDF/Imágenes (CV, ID, Títulos, Contratos) vinculados a Empleados o Candidatos.
*   **Gestión de Ausencias:** Registro de bajas autorizadas (Vacaciones, Enfermedad, Permiso personal) con fechas de inicio y fin.
*   **Sincronización Biométrico:** Vinculación de Empleados con su `user_id` en el dispositivo físico, y opción de dar de alta ("Crear en equipo") remotamente.

### 2.3 Módulo de Reportes y Nómina
*   **Dashboard:** KPIs del panel (total, llegaron, faltaron, llegaron tarde).
*   **Reportes Diarios / Mensuales:** Reportes de asistencia general, llegadas tarde, ausencias prolongadas e incumplimientos.
*   **Nómina:** Generación de periodos de nómina (`NominaPeriodo` y `NominaEmpleado`), calculos de salario base vs descuentos por ausencias o ingresos adicionales.
*   **Exportación PDF:** Generación visual (usando `reportlab`) de todos los reportes operativos y volantes de nómina.

---

## 3. Lista de Tareas y Mejoras Pendientes

- [ ] **Limpieza de Código Muerto (App Usuarios):** Evaluar si la app huérfana temporal de `usuarios` se eliminará del código fuente o si se conectará para reactivar el sistema de Roles.
- [ ] **Refactorización de Controladores de Reportes:** Mover la lógica de generación de archivos PDF (casi 2,000 líneas en `reportes/views.py`) a clases de servicio (`services/pdf_builder.py`) para mejor mantenibilidad.
- [ ] **Sincronización en Segundo Plano:** Automatizar (por vía de Cron o Celery) la descarga periódica de registros desde los biométricos para evitar el botón de "sincronización manual".
- [ ] **Validaciones de Base de Datos:** Configurar el Django para que se conecte directamente al servidor PostgreSQL `192.168.20.3` en entornos de desarrollo y staging para replicar el entorno de `192.168.20.7`
- [ ] **Scripts de Despliegue:** Crear un script Bash `.sh` estándar que ejecute `git pull`, `pip install`, `python manage.py migrate` y reinicio de servicios automáticamente en el servidor `192.168.20.7`.
