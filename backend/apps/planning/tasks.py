from celery import shared_task


@shared_task
def checkpoint_reminders():
    from .services import send_checkpoint_reminders

    return send_checkpoint_reminders()
