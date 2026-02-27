import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util
from django.utils import timezone

logger = logging.getLogger(__name__)

# Import the logic we already have
from dispositivos.management.commands.sync_biometricos import Command as SyncCommand

def sync_biometricos_job():
    """
    Este es el 'job' que ejecuta APScheduler. Llama directamente al handle del comando 'sync_biometricos'.
    """
    try:
        cmd = SyncCommand()
        cmd.handle()
    except Exception as e:
        logger.error(f"Error corriendo el trabajo programado de sincronización: {e}")

@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """
    Elimina registros de ejecución viejos para que la base de datos no se llene (max 7 días).
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)

class Command(BaseCommand):
    help = "Inicia el planificador (APScheduler) para correr tareas en segundo plano."

    def handle(self, *args, **options):
        # Usamos Use_TZ timezone para apscheduler
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # Configurar la tarea principal: ejecutar cada 1 hora.
        # Puedes cambiar 'hours=1' por 'minutes=60' o usar CronTrigger
        scheduler.add_job(
            sync_biometricos_job,
            trigger=IntervalTrigger(hours=1),
            id="sync_biometricos_cada_hora",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Añadido el trabajo 'sync_biometricos_cada_hora' al scheduler.")

        # Configurar la tarea de limpieza: cada lunes a la medianoche (opcional, buena limpieza)
        scheduler.add_job(
            delete_old_job_executions,
            trigger=IntervalTrigger(days=7),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Añadida tarea de limpieza 'delete_old_job_executions'.")

        try:
            logger.info("Iniciando scheduler...")
            self.stdout.write(self.style.SUCCESS("Scheduler iniciado. Presiona Ctrl+C para salir."))
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Deteniendo scheduler...")
            scheduler.shutdown()
            self.stdout.write(self.style.SUCCESS("Scheduler detenido exitosamente."))
