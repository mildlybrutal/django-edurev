from django.db import models


class Portal(models.TextChoices):
    INTERNAL = "internal", "Internal (students, faculty, placement cell, admin)"
    RECRUITER = "recruiter", "Recruiter"
