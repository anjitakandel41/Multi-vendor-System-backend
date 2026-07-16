# accounts/emails.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_verification_email(user, token: str):
    """Send email verification link to newly registered user."""
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    subject = "Verify your Inventory Management API account"

    try:
        html_message = render_to_string('accounts/emails/verification.html', {
            'username': user.username,
            'verification_url': verification_url,
            'site_name': getattr(settings, 'SITE_NAME', 'Your App'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        })
    except:
        html_message = None

    plain_message = f"Click this link to verify your email: {verification_url}"

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_password_reset_email(user, reset_token: str):
    """
    Send password reset link to user.
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    subject = "Reset your Inventory Management API password"

    context = {
        'username': user.username,
        'reset_url': reset_url,
        'token': reset_token,
        'site_name': getattr(settings, 'SITE_NAME', 'Your App'),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        'expiry_hours': getattr(settings, 'PASSWORD_RESET_TIMEOUT', 24),
    }

    try:
        html_message = render_to_string('accounts/emails/reset_password.html', context)
    except:
        html_message = None

    plain_message = f"""
    Hello {user.username},
    
    You requested to reset your password for {getattr(settings, 'SITE_NAME', 'Your App')}.
    
    Click this link to reset your password:
    {reset_url}
    
    This link will expire in {getattr(settings, 'PASSWORD_RESET_TIMEOUT', 24)} hours.
    
    If you didn't request this, please ignore this email.
    
    Best regards,
    {getattr(settings, 'SITE_NAME', 'Your App')} Team
    """

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_password_reset_confirmation(user):
    """
    Send confirmation email after password is successfully reset.
    """
    subject = "Your password has been changed"

    context = {
        'username': user.username,
        'site_name': getattr(settings, 'SITE_NAME', 'Your App'),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        'login_url': f"{settings.FRONTEND_URL}/login",
    }

    try:
        html_message = render_to_string('accounts/emails/password_reset_confirmation.html', context)
    except:
        html_message = None

    plain_message = f"""
    Hello {user.username},
    
    Your password for {getattr(settings, 'SITE_NAME', 'Your App')} has been successfully changed.
    
    If you didn't make this change, please contact our support team immediately at {getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)}.
    
    Login here: {settings.FRONTEND_URL}/login
    
    Best regards,
    {getattr(settings, 'SITE_NAME', 'Your App')} Team
    """

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_welcome_email(user):
    """
    Send welcome email to new user.
    """
    subject = f"Welcome to {getattr(settings, 'SITE_NAME', 'Your App')}!"

    context = {
        'username': user.username,
        'site_name': getattr(settings, 'SITE_NAME', 'Your App'),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        'login_url': f"{settings.FRONTEND_URL}/login",
    }

    try:
        html_message = render_to_string('accounts/emails/welcome.html', context)
    except:
        html_message = None

    plain_message = f"""
    Hello {user.username},
    
    Welcome to {getattr(settings, 'SITE_NAME', 'Your App')}!
    
    We're excited to have you on board. You can now log in to your account:
    {settings.FRONTEND_URL}/login
    
    If you have any questions, feel free to contact us at {getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)}.
    
    Best regards,
    {getattr(settings, 'SITE_NAME', 'Your App')} Team
    """

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )