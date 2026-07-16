# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from cloudinary.models import CloudinaryField
from django.utils import timezone
import uuid

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
    )
    
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    is_email_verified = models.BooleanField(default=False)
    
    # Password reset fields
    reset_password_token = models.CharField(max_length=100, blank=True, null=True)
    reset_password_token_created_at = models.DateTimeField(blank=True, null=True)
    
    # Employee management fields
    is_active = models.BooleanField(default=True)  # Already in AbstractUser, but keeping explicit
    is_staff = models.BooleanField(default=False)  # Already in AbstractUser
    is_superuser = models.BooleanField(default=False)  # Already in AbstractUser
    
    def is_admin_user(self):
        return self.role == 'admin'
    
    def is_vendor(self):
        """Check if user is a vendor (store owner)"""
        return self.role == 'vendor' or (self.role == 'admin' and hasattr(self, 'owned_tenant'))
    
    def is_employee(self):
        """Check if user is an employee of any store"""
        from tenants.models import TenantMember
        return TenantMember.objects.filter(user=self, is_active=True).exists()
    
    def get_employee_role(self, tenant_slug=None):
        """Get employee role for a specific tenant"""
        from tenants.models import TenantMember, Tenant
        if tenant_slug:
            try:
                tenant = Tenant.objects.get(slug=tenant_slug)
                member = TenantMember.objects.get(tenant=tenant, user=self, is_active=True)
                return member.role
            except:
                return None
        return None
    
    def get_tenant_memberships(self):
        """Get all store memberships for this user"""
        from tenants.models import TenantMember
        return TenantMember.objects.filter(user=self, is_active=True).select_related('tenant')
    
    def generate_reset_token(self):
        """Generate a unique reset token"""
        self.reset_password_token = str(uuid.uuid4())
        self.reset_password_token_created_at = timezone.now()
        self.save(update_fields=['reset_password_token', 'reset_password_token_created_at'])
        return self.reset_password_token
    
    def is_reset_token_valid(self):
        """Check if the reset token is still valid"""
        from django.conf import settings
        from datetime import timedelta
        
        if not self.reset_password_token or not self.reset_password_token_created_at:
            return False
        
        expiry_time = self.reset_password_token_created_at + timedelta(
            hours=getattr(settings, 'PASSWORD_RESET_TIMEOUT', 24)
        )
        return timezone.now() <= expiry_time
    
    def save(self, *args, **kwargs):
        # Auto-set role for staff users
        if self.is_staff:
            self.role = 'admin'
            self.is_email_verified = True
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f'{self.username} ({self.role})'


class Profile(models.Model):
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    avatar = CloudinaryField('avatar', null=True, blank=True, folder='avatars/')
    avatar_url = models.URLField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    
    # Additional profile fields for employees
    bio = models.TextField(null=True, blank=True, help_text="Short bio about the employee")
    designation = models.CharField(max_length=100, null=True, blank=True, help_text="Job title")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10, 
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        null=True, 
        blank=True
    )
    emergency_contact = models.CharField(max_length=20, null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def _generate_avatar_url(self):
        name = self.user.get_full_name() or self.user.username
        initials = '+'.join(name.split()[:2])
        return (
            f'https://ui-avatars.com/api/'
            f'?name={initials}'
            f'&size=200'
            f'&background=60BB46'
            f'&color=ffffff'
            f'&bold=true'
            f'&rounded=true'
        )

    def save(self, *args, **kwargs):
        if not self.avatar and not self.avatar_url:
            self.avatar_url = self._generate_avatar_url()
        super().save(*args, **kwargs)

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return self.avatar_url or self._generate_avatar_url()

    def __str__(self):
        return f'{self.user.username} profile'


# ============================================
# ADDITIONAL MODELS FOR EMPLOYEE MANAGEMENT
# ============================================

class EmployeeInvitation(models.Model):
    """
    Model to track employee invitations sent by vendors
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    )
    
    email = models.EmailField()
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='invitations')
    invited_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_invitations')
    role = models.CharField(max_length=20, choices=[('manager', 'Manager'), ('staff', 'Staff'), ('viewer', 'Viewer')])
    
    token = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    invited_user = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='accepted_invitations'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['email', 'tenant']  # Prevent duplicate invitations
    
    def __str__(self):
        return f'Invitation for {self.email} to {self.tenant.name}'
    
    def is_expired(self):
        """Check if invitation has expired"""
        return timezone.now() > self.expires_at
    
    def accept(self, user):
        """Accept the invitation and add user to tenant"""
        from tenants.models import TenantMember
        
        if self.status != 'pending':
            raise ValueError(f'Invitation status is {self.status}, not pending')
        
        if self.is_expired():
            self.status = 'expired'
            self.save()
            raise ValueError('Invitation has expired')
        
        # Add user to tenant
        TenantMember.objects.create(
            tenant=self.tenant,
            user=user,
            role=self.role,
            added_by=self.invited_by,
            is_active=True
        )
        
        self.status = 'accepted'
        self.invited_user = user
        self.accepted_at = timezone.now()
        self.save()
        
        return user


class EmployeeActivityLog(models.Model):
    """
    Model to track employee activities for auditing
    """
    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('export', 'Export'),
        ('import', 'Import'),
    )
    
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activity_logs')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='employee_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=100)  # e.g., 'product', 'order', 'inventory'
    resource_id = models.IntegerField(null=True, blank=True)
    details = models.JSONField(default=dict)  # Store additional details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]
    
    def __str__(self):
        return f'{self.employee.username} - {self.action} at {self.created_at}'