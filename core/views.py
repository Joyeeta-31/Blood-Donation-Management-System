# core/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Q
from django.db import transaction
from django.views.decorators.http import require_POST
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
from django.views.decorators.csrf import csrf_exempt

from .models import (
    User, DonorProfile, BloodBank, BloodInventory,
    DonationRequest, DonationHistory, BLOOD_GROUPS
)
from .serializers import (
    UserSerializer, DonorProfileSerializer,
    BloodBankSerializer, BloodInventorySerializer,
    DonationRequestSerializer, DonationHistorySerializer
)
from rest_framework.permissions import IsAuthenticated, IsAdminUser

# ---------- API viewsets ----------

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        if self.action == 'retrieve':
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated or not user.is_staff:
            return User.objects.filter(pk=user.pk) if user and user.is_authenticated else User.objects.none()
        return super().get_queryset()


class BloodBankViewSet(viewsets.ModelViewSet):
    queryset = BloodBank.objects.all()
    serializer_class = BloodBankSerializer
    permission_classes = [IsAdminUser]


class BloodInventoryViewSet(viewsets.ModelViewSet):
    queryset = BloodInventory.objects.all()
    serializer_class = BloodInventorySerializer
    permission_classes = [IsAdminUser]


class DonationRequestViewSet(viewsets.ModelViewSet):
    queryset = DonationRequest.objects.all()
    serializer_class = DonationRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'admin':
            return DonationRequest.objects.all().order_by('-created_at')
        return DonationRequest.objects.filter(requester=user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status != 'pending':
            return Response({"detail": "Already processed."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # select inventory for this blood group
            inv = BloodInventory.objects.select_for_update().filter(blood_group=req.blood_group).first()
            if not inv:
                return Response({"detail": "No inventory available for this blood group."}, status=status.HTTP_400_BAD_REQUEST)

            if inv.units >= req.units:
                inv.units -= req.units
                inv.save()

                req.status = 'approved'
                req.approved_by = request.user
                req.save()

                DonationHistory.objects.create(
                    donor=req.requester,
                    blood_group=req.blood_group,
                    units=req.units,
                    blood_bank=inv.blood_bank
                )

                return Response({"detail": "Approved"}, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Not enough units"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        req = self.get_object()
        if req.status != 'pending':
            return Response({"detail": "Already processed."}, status=status.HTTP_400_BAD_REQUEST)
        req.status = 'rejected'
        req.approved_by = request.user
        req.save()
        return Response({"detail": "Rejected"}, status=status.HTTP_200_OK)


class DonationHistoryViewSet(viewsets.ModelViewSet):
    queryset = DonationHistory.objects.all()
    serializer_class = DonationHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return DonationHistory.objects.all().order_by('-donated_at')
        return DonationHistory.objects.filter(donor=user).order_by('-donated_at')

    def perform_create(self, serializer):
        serializer.save(donor=self.request.user)


# ---------- Template views ----------

def home(request):
    return render(request, 'core/home.html')


def user_register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        blood_group = request.POST.get('blood_group')

        if not username or not email or not password:
            messages.error(request, 'Please fill all required fields.')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already used.')
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role='donor'
        )

        if blood_group in [b[0] for b in BLOOD_GROUPS]:
            profile, created = DonorProfile.objects.get_or_create(user=user, defaults={'blood_group': blood_group})
            if not created:
                profile.blood_group = blood_group
                profile.save()

        login(request, user)
        return redirect('dashboard')

    blood_groups = [b[0] for b in BLOOD_GROUPS]
    return render(request, 'core/register.html', {'blood_groups': blood_groups})


def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Please enter email and password.')
            return redirect('login')

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user:
            login(request, user)
            return redirect('dashboard')

        messages.error(request, 'Invalid credentials')
        return redirect('login')

    return render(request, 'core/login.html')


@login_required
def user_logout(request):
    logout(request)
    return redirect('home')


@login_required
def dashboard(request):
    user = request.user
    if user.is_staff or user.role == 'admin':
        total_donors = User.objects.filter(role='donor').count()
        inventory_by_group = BloodInventory.objects.values('blood_group').annotate(total_units=Sum('units'))
        pending_requests = DonationRequest.objects.filter(status='pending').count()
        context = {
            'total_donors': total_donors,
            'inventory_by_group': inventory_by_group,
            'pending_requests': pending_requests,
        }
        return render(request, 'core/admin_dashboard.html', context)
    else:
        profile = getattr(user, 'donor_profile', None)
        donation_history = DonationHistory.objects.filter(donor=user).order_by('-donated_at')
        available = BloodInventory.objects.values('blood_group').annotate(total_units=Sum('units'))
        context = {
            'profile': profile,
            'donation_history': donation_history,
            'available': available,
        }
        return render(request, 'core/donor_dashboard.html', context)


@login_required
def make_request(request):
    if request.method == 'POST':
        bg = request.POST.get('blood_group')
        units_raw = request.POST.get('units') or '1'
        city = request.POST.get('city', '')
        hospital = request.POST.get('hospital_name', '')

        try:
            units = int(units_raw)
        except ValueError:
            messages.error(request, 'Invalid units value.')
            return redirect('make_request')

        if bg not in [b[0] for b in BLOOD_GROUPS] or units <= 0:
            messages.error(request, 'Invalid blood group or units.')
            return redirect('make_request')

        DonationRequest.objects.create(
            requester=request.user,
            blood_group=bg,
            units=units,
            city=city,
            hospital_name=hospital
        )
        messages.success(request, 'Request submitted.')
        return redirect('dashboard')

    return render(request, 'core/make_request.html', {'blood_groups': [b[0] for b in BLOOD_GROUPS]})


@login_required
def search_donors(request):
    q = request.GET.get('q', '').strip()
    results = DonorProfile.objects.filter(
        Q(blood_group__iexact=q) | Q(city__icontains=q)
    ) if q else []
    return render(request, 'core/search.html', {'results': results, 'q': q})


@login_required
def edit_profile(request):
    user = request.user
    profile, _ = DonorProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.save()

        profile.phone = request.POST.get('phone', '').strip()
        profile.city = request.POST.get('city', '').strip()
        bg = request.POST.get('blood_group', profile.blood_group)
        if bg in [b[0] for b in BLOOD_GROUPS]:
            profile.blood_group = bg

        if request.FILES.get('profile_photo'):
            profile.profile_photo = request.FILES.get('profile_photo')
        profile.save()

        messages.success(request, 'Profile updated.')
        return redirect('dashboard')

    return render(request, 'core/edit_profile.html', {
        'profile': profile,
        'blood_groups': [b[0] for b in BLOOD_GROUPS],
    })


# ---------- Admin template views ----------

def staff_required(view_func):
    return user_passes_test(lambda u: u.is_active and u.is_staff)(view_func)


@staff_required
def admin_requests(request):
    requests_qs = DonationRequest.objects.all().order_by('-created_at')
    return render(request, 'core/admin_requests.html', {'requests': requests_qs})


@require_POST
@staff_required
def admin_request_approve(request, pk):
    req = get_object_or_404(DonationRequest, pk=pk)
    if req.status != 'pending':
        messages.warning(request, 'Request already processed.')
        return redirect('admin_requests')

    with transaction.atomic():
        inv = BloodInventory.objects.select_for_update().filter(blood_group=req.blood_group).first()
        if not inv:
            messages.error(request, 'No inventory for this blood group.')
            return redirect('admin_requests')

        if inv.units >= req.units:
            inv.units -= req.units
            inv.save()

            req.status = 'approved'
            req.approved_by = request.user
            req.save()

            DonationHistory.objects.create(
                donor=req.requester,
                blood_group=req.blood_group,
                units=req.units,
                blood_bank=inv.blood_bank
            )

            messages.success(request, 'Request approved.')
        else:
            messages.error(request, 'Not enough units.')
    return redirect('admin_requests')


@require_POST
@staff_required
def admin_request_reject(request, pk):
    req = get_object_or_404(DonationRequest, pk=pk)
    if req.status != 'pending':
        messages.warning(request, 'Request already processed.')
        return redirect('admin_requests')
    req.status = 'rejected'
    req.approved_by = request.user
    req.save()
    messages.success(request, 'Request rejected.')
    return redirect('admin_requests')


@staff_required
def admin_donors(request):
    donors = User.objects.filter(role='donor').order_by('username')
    donor_profiles = DonorProfile.objects.filter(user__in=donors).select_related('user')
    return render(request, 'core/admin_donors.html', {'donors': donor_profiles})


# ---------- Signals for auto inventory ----------

@receiver(post_save, sender=BloodBank)
def create_inventory_for_new_bank(sender, instance, created, **kwargs):
    if created:
        for bg, _ in BLOOD_GROUPS:
            BloodInventory.objects.get_or_create(
                blood_bank=instance,
                blood_group=bg,
                defaults={'units': 10}  # default starting units
            )

@staff_required
def manage_inventory(request):
    inventories = BloodInventory.objects.select_related('blood_bank').all().order_by('blood_bank__name', 'blood_group')

    if request.method == 'POST':
        inventory_id = request.POST.get('inventory_id')
        units = request.POST.get('units')

        try:
            inv = BloodInventory.objects.get(id=inventory_id)
            inv.units = int(units)
            inv.save()
            messages.success(request, f"{inv.blood_bank.name} - {inv.blood_group} updated to {units} units.")
        except BloodInventory.DoesNotExist:
            messages.error(request, "Inventory record not found.")
        except ValueError:
            messages.error(request, "Invalid units value.")

        return redirect('manage_inventory')

    context = {
        'inventories': inventories
    }
    return render(request, 'core/manage_inventory.html', context)


@require_POST
@staff_required
def update_inventory(request, pk):
    inv = get_object_or_404(BloodInventory, pk=pk)
    try:
        units = int(request.POST.get('units', inv.units))
        if units < 0:
            messages.error(request, 'Units cannot be negative.')
        else:
            inv.units = units
            inv.save()
            messages.success(request, f'{inv.blood_group} units updated.')
    except ValueError:
        messages.error(request, 'Invalid units value.')
    return redirect('manage_inventory')