from django.contrib import admin
from .models import User, BloodBank, DonorProfile, BloodInventory, DonationRequest, DonationHistory
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff')

admin.site.register(BloodBank)
admin.site.register(DonorProfile)
admin.site.register(BloodInventory)
admin.site.register(DonationRequest)
admin.site.register(DonationHistory)
