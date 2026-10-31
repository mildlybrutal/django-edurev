from celery import shared_task


@shared_task
def ping():
    """Smoke-test task used to confirm the worker is consuming the queue."""
    return "pong"
