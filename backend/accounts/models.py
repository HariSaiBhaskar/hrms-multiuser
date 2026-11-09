"""Users, roles, audit trail and shared announcements.

The single most important idea in this file: **every user is a row in one
shared database**. Two people logged in on two laptops read and write the same
tables, so a change made by HR is visible to everyone else on their next
refresh. Nothing is stored in the browser.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrator"
    HR = "HR", "HR Officer"
    MANAGER = "MANAGER", "Manager"
    EMPLOYEE = "EMPLOYEE", "Employee"


# Roles allowed to create/edit employee records and see everyone's data.
PEOPLE_MANAGERS = (Role.ADMIN, Role.HR)


class UserManager(BaseUserManager):
    """Email is the login field, so the stock username manager doesn't fit."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.EMPLOYEE)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """A person who can log in. Role decides what they are allowed to do."""

    username = None  # replaced by email
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=120)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    phone = models.CharField(max_length=20, blank=True)
    job_title = models.CharField(max_length=80, blank=True)
    must_change_password = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["role"])]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    # -- role helpers used by permissions and serializers -------------------
    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_superuser

    @property
    def is_hr_role(self):
        return self.role == Role.HR

    @property
    def is_manager_role(self):
        return self.role == Role.MANAGER

    @property
    def can_manage_people(self):
        """Admin/HR: full read + write over every employee record."""
        return self.is_admin_role or self.is_hr_role

    @property
    def can_approve_leave(self):
        return self.is_admin_role or self.is_hr_role or self.is_manager_role

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return (self.full_name or self.email).split(" ")[0]


class AuditLog(models.Model):
    """Append-only trail of who changed what.

    Gives the shared workspace a visible activity feed and makes the
    "every change reaches every user" requirement something you can *see*.
    """

    class Action(models.TextChoices):
        LOGIN = "LOGIN", "Signed in"
        LOGOUT = "LOGOUT", "Signed out"
        CREATE = "CREATE", "Created"
        UPDATE = "UPDATE", "Updated"
        DELETE = "DELETE", "Deleted"
        APPROVE = "APPROVE", "Approved"
        REJECT = "REJECT", "Rejected"
        CHECK_IN = "CHECK_IN", "Checked in"
        CHECK_OUT = "CHECK_OUT", "Checked out"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_entries",
    )
    action = models.CharField(max_length=12, choices=Action.choices)
    entity = models.CharField(max_length=40)          # "employee", "leave_request", ...
    entity_id = models.CharField(max_length=40, blank=True)
    summary = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor} {self.action} {self.entity}"

    @classmethod
    def record(cls, actor, action, entity, summary, entity_id=""):
        return cls.objects.create(
            actor=actor if getattr(actor, "pk", None) else None,
            action=action, entity=entity, entity_id=str(entity_id or ""),
            summary=summary[:255],
        )


class Announcement(models.Model):
    """Company-wide notice. Every authenticated user can read it."""

    title = models.CharField(max_length=140)
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="announcements",
    )
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title
