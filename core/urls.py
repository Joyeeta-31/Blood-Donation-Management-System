# core/urls.py
from django.urls import path, include
from rest_framework import routers
from . import views

# DRF Router for API
router = routers.DefaultRouter()
router.register(r'api/users', views.UserViewSet, basename='api-users')
router.register(r'api/bloodbanks', views.BloodBankViewSet, basename='api-bloodbanks')
router.register(r'api/inventory', views.BloodInventoryViewSet, basename='api-inventory')
router.register(r'api/requests', views.DonationRequestViewSet, basename='api-requests')
router.register(r'api/history', views.DonationHistoryViewSet, basename='api-history')

urlpatterns = [
    # Home & Authentication (Templates)
    path('', views.home, name='home'),
    path('register/', views.user_register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Donor actions
    path('make_request/', views.make_request, name='make_request'),
    path('search_donors/', views.search_donors, name='search_donors'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),

    # Admin template views
    path('custom_admin/requests/', views.admin_requests, name='admin_requests'),
    path('custom_admin/requests/approve/<int:pk>/', views.admin_request_approve, name='admin_request_approve'),
    path('custom_admin/requests/reject/<int:pk>/', views.admin_request_reject, name='admin_request_reject'),
    path('custom_admin/donors/', views.admin_donors, name='admin_donors'),
    path('custom_admin/inventory/', views.manage_inventory, name='manage_inventory'),
    path('custom_admin/inventory/update/<int:pk>/', views.update_inventory, name='update_inventory'),



    # DRF API endpoints
    path('', include(router.urls)),
]
