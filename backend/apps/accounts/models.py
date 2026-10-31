from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import Institution


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Login is by email. Roles are Django groups; see apps.accounts.roles."""

    username = None
    email = models.EmailField("email address", unique=True)
    # Nullable only for platform superusers; every other account belongs to an institution.
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.PROTECT, related_name="users")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)
        if not self.is_superuser and self.institution_id is None:
            raise ValidationError({"institution": "Non-superuser accounts must belong to an institution."})


class TOTPDevice(models.Model):
    """One authenticator per user. `confirmed_at` is set once the user proves possession."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="totp")
    secret = models.CharField(max_length=64)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_counter = models.BigIntegerField(null=True, blank=True, help_text="Last accepted time step (anti-replay).")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TOTP for {self.user_id}"

    @property
    def is_confirmed(self):
        return self.confirmed_at is not None
