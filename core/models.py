# core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.conf import settings

BLOOD_GROUPS = [
    ('A+', 'A+'), ('A-', 'A-'),
    ('B+', 'B+'), ('B-', 'B-'),
    ('O+', 'O+'), ('O-', 'O-'),
    ('AB+', 'AB+'), ('AB-', 'AB-'),
]

ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('donor', 'Donor'),
    ('hospital', 'Hospital'),
]


class User(AbstractUser):
    """
    Custom user model. Note: setting email unique=True requires care if you already
    have users with duplicate emails in the DB before applying this migration.
    """
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='donor')
    email = models.EmailField(_('email address'), unique=True)

    def __str__(self):
        return self.username


class BloodBank(models.Model):
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=120, blank=True, null=True)
    address = models.TextField(blank=True)
    contact = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.name} - {self.city or 'No city'}"


class DonorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='donor_profile')
    phone = models.CharField(max_length=20, blank=True)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS, blank=True, null=True)
    city = models.CharField(max_length=120, blank=True)
    last_donated = models.DateField(blank=True, null=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        bg = self.blood_group or "N/A"
        name = self.user.get_full_name() or self.user.username
        return f"{name} ({bg})"


class BloodInventory(models.Model):
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS)
    units = models.PositiveIntegerField(default=0)
    blood_bank = models.ForeignKey(BloodBank, on_delete=models.CASCADE, related_name='inventory')

    class Meta:
        unique_together = ('blood_group', 'blood_bank')
        ordering = ['blood_bank__name', 'blood_group']

    def __str__(self):
        return f"{self.blood_bank.name} - {self.blood_group}: {self.units}"


REQUEST_STATUS = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class DonationRequest(models.Model):
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS)
    units = models.PositiveIntegerField(default=1)
    city = models.CharField(max_length=120, blank=True)
    hospital_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')

    def __str__(self):
        return f"{self.requester.username} needs {self.units} units ({self.blood_group}) - {self.status}"


class DonationHistory(models.Model):
    """
    Records an actual donation event. donated_at is auto-set when the record is created.
    If you need to store historical dates from the past, remove auto_now_add and pass the date explicitly.
    """
    donor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='donation_history')
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS)
    units = models.PositiveIntegerField(default=1)
    donated_at = models.DateTimeField(auto_now_add=True)
    blood_bank = models.ForeignKey(BloodBank, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.donor.username} gave {self.units} units on {self.donated_at.date()}"
