# accounts/urls.py
from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    AdminLoginView,
    VendorRegisterView,
    VendorLoginView,
    EmployeeLoginView,
    MeView,
    ChangePasswordView,
    LogoutView,
    ProfileView,
    ForgotPasswordView,
    ResetPasswordView,
    # Employee management views
    VendorCreateEmployeeView,
    VendorListEmployeesView,
    VendorGetEmployeeView,
    VendorUpdateEmployeeView,
    VendorRemoveEmployeeView,
    VendorBulkCreateEmployeesView,
)
from .google_auth import GoogleAuthView
from .jwt_views import CustomTokenRefreshView

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('vendor/register/', VendorRegisterView.as_view(), name='vendor-register'),
    path('vendor/login/', VendorLoginView.as_view(), name='vendor-login'),
    path('employee/login/', EmployeeLoginView.as_view(), name='employee-login'),
    
    # User
    path('me/', MeView.as_view(), name='me'),
    path('profile/', ProfileView.as_view(), name='profile'),
    
    # Password Management
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Password Reset
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/<str:token>/', ResetPasswordView.as_view(), name='reset-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password-no-token'),
    
    # Token Refresh
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    
    # Google OAuth
    path('google/login/', GoogleAuthView.as_view(), name='google-login'),
    
    # ============================================
    # VENDOR EMPLOYEE MANAGEMENT
    # ============================================
    path('vendor/employees/', VendorListEmployeesView.as_view(), name='vendor-employees-list'),
    path('vendor/employees/create/', VendorCreateEmployeeView.as_view(), name='vendor-employees-create'),
    path('vendor/employees/bulk-create/', VendorBulkCreateEmployeesView.as_view(), name='vendor-employees-bulk-create'),
    path('vendor/employees/<int:employee_id>/', VendorGetEmployeeView.as_view(), name='vendor-employees-detail'),
    path('vendor/employees/<int:employee_id>/update/', VendorUpdateEmployeeView.as_view(), name='vendor-employees-update'),
    path('vendor/employees/<int:employee_id>/remove/', VendorRemoveEmployeeView.as_view(), name='vendor-employees-remove'),
]