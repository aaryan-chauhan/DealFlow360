import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(UUIDModel, TimeStampedModel):
    """Tenant root. Every tenant-scoped row hangs off a company."""

    name = models.CharField(max_length=255)

    class Meta:
        db_table = "company"
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    """Internal staff only (rep / manager / finance / admin). Customers live in `Customer`."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "user"
        ordering = ["email"]

    def __str__(self):
        return self.email


class Role(UUIDModel, TimeStampedModel):
    SALES_REP = "sales_rep"
    SALES_MANAGER = "sales_manager"
    FINANCE_OPS = "finance_ops"
    ADMIN = "admin"

    CODE_CHOICES = [
        (SALES_REP, "Sales Rep"),
        (SALES_MANAGER, "Sales Manager"),
        (FINANCE_OPS, "Finance / Ops"),
        (ADMIN, "Admin"),
    ]

    code = models.CharField(max_length=50, unique=True, choices=CODE_CHOICES)
    label = models.CharField(max_length=100)

    class Meta:
        db_table = "role"
        ordering = ["code"]

    def __str__(self):
        return self.label


class Membership(UUIDModel, TimeStampedModel):
    """user x company x role — one person can hold a different role in each company."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="memberships")
    is_active_default = models.BooleanField(default=False)

    class Meta:
        db_table = "membership"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"], name="uniq_membership_user_company"
            )
        ]
        ordering = ["-is_active_default", "company__name"]

    def __str__(self):
        return f"{self.user.email} @ {self.company.name} ({self.role.code})"


class Customer(UUIDModel, TimeStampedModel):
    """The external buying party. Never a `User` — portal access is quotation-scoped."""

    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"
    TIER_CHOICES = [(BRONZE, BRONZE), (SILVER, SILVER), (GOLD, GOLD)]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="customers"
    )
    name = models.CharField(max_length=255)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=BRONZE)
    email = models.EmailField()
    location = models.CharField(max_length=128, blank=True)
    password_hash = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "customer"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "email"], name="uniq_customer_company_email"
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.tier})"
