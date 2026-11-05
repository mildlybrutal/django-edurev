from celery import shared_task


@shared_task
def deliver_broadcast(broadcast_id):
    from .services import deliver_broadcast as deliver

    return deliver(broadcast_id)
