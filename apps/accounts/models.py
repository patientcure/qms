from django.contrib.auth.models import AbstractUser
from django.db import models

class Roles(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    SALESPERSON = 'SALESPERSON', 'Salesperson'

class User(AbstractUser):
    # We'll use username for admin login convenience; email unique for communications
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.SALESPERSON)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"
