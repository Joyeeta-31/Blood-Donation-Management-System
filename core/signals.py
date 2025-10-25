from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, DonorProfile, BloodBank, BLOOD_GROUPS, BloodInventory

# ----------------- Create donor profile -----------------
@receiver(post_save, sender=User)
def create_profile_for_donor(sender, instance, created, **kwargs):
    if created and instance.role == 'donor':
        DonorProfile.objects.create(user=instance)

# ----------------- Auto-fill inventory for new BloodBank -----------------
@receiver(post_save, sender=BloodBank)
def create_inventory_for_new_bank(sender, instance, created, **kwargs):
    if created:
        for bg, _ in BLOOD_GROUPS:
            BloodInventory.objects.get_or_create(
                blood_bank=instance,
                blood_group=bg,
                defaults={'units': 10}  # default units for each blood group
            )
