from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.exceptions import ValidationError
from datetime import timedelta
import uuid
import json
import logging

from .models import User, EmailVerificationToken, PasswordResetToken, ActivityLog, UserSession
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, CustomPasswordResetForm,
    CustomSetPasswordForm, UserProfileForm, GitHubTokenForm, UserPreferencesForm
)
from .utils import get_client_ip, log_user_activity

logger = logging.getLogger(__name__)


def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create email verification token
            token = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(days=1)
            
            EmailVerificationToken.objects.create(
                user=user,
                token=token,
                expires_at=expires_at
            )
            
            # Send verification email
            try:
                verification_url = request.build_absolute_uri(
                    reverse('verify_email', kwargs={'token': token})
                )
                
                subject = 'Verify your FDS account'
                html_message = render_to_string('dev_productivity/auth/verification_email.html', {
                    'user': user,
                    'verification_url': verification_url,
                    'site_name': 'FDS Analyzer'
                })
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False
                )
                
                messages.success(
                    request,
                    f'Account created successfully! Please check your email ({user.email}) to verify your account.'
                )
                
                # Log activity
                log_user_activity(user, 'register', 'User registered', request)
                
                return redirect('login')
                
            except Exception as e:
                logger.error(f"Failed to send verification email to {user.email}: {e}")
                messages.warning(
                    request,
                    'Account created but verification email could not be sent. Please contact support.'
                )
                return redirect('login')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'dev_productivity/auth/register.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        # Simple debug login - bypass custom form
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        remember_me = request.POST.get('remember_me', False)
        
        if username_or_email and password:
            # Try authentication with email first, then username
            user = None
            if '@' in username_or_email:
                user = authenticate(request, username=username_or_email, password=password)
            
            if not user:
                # Try with username
                user = authenticate(request, username=username_or_email, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Set session expiry
                    if remember_me:
                        request.session.set_expiry(1209600)  # 2 weeks
                    else:
                        request.session.set_expiry(0)  # Browser session
                    
                    # Update user info
                    user.last_login_ip = get_client_ip(request)
                    user.save(update_fields=['last_login_ip'])
                    
                    # Create/update user session
                    session_key = request.session.session_key
                    if session_key:
                        UserSession.objects.update_or_create(
                            session_key=session_key,
                            defaults={
                                'user': user,
                                'ip_address': get_client_ip(request),
                                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                                'last_activity': timezone.now()
                            }
                        )
                    
                    # Log activity
                    log_user_activity(user, 'login', 'User logged in', request)
                    
                    messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                    
                    # Redirect to next or dashboard
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    return redirect('user_dashboard')
                else:
                    messages.error(request, 'Your account is inactive. Please contact support.')
            else:
                messages.error(request, 'Invalid email/username or password.')
        else:
            messages.error(request, 'Please enter both email/username and password.')
    
    # Create a simple form for display
    form = CustomAuthenticationForm()
    
    return render(request, 'dev_productivity/auth/login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout view"""
    user = request.user
    
    # Log activity before logout
    log_user_activity(user, 'logout', 'User logged out', request)
    
    # Clear user session
    session_key = request.session.session_key
    if session_key:
        UserSession.objects.filter(session_key=session_key).delete()
    
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')


def verify_email(request, token):
    """Email verification view"""
    try:
        verification_token = get_object_or_404(EmailVerificationToken, token=token)
        
        if verification_token.is_expired():
            messages.error(request, 'Verification link has expired. Please request a new one.')
            return redirect('resend_verification')
        
        user = verification_token.user
        user.email_verified = True
        user.save()
        
        # Delete the verification token
        verification_token.delete()
        
        messages.success(request, 'Email verified successfully! You can now log in.')
        return redirect('login')
        
    except Exception as e:
        logger.error(f"Email verification failed for token {token}: {e}")
        messages.error(request, 'Invalid or expired verification link.')
        return redirect('login')


def resend_verification(request):
    """Resend email verification"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        try:
            user = User.objects.get(email=email, email_verified=False)
            
            # Delete old tokens
            EmailVerificationToken.objects.filter(user=user).delete()
            
            # Create new token
            token = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(days=1)
            
            EmailVerificationToken.objects.create(
                user=user,
                token=token,
                expires_at=expires_at
            )
            
            # Send verification email
            verification_url = request.build_absolute_uri(
                reverse('verify_email', kwargs={'token': token})
            )
            
            subject = 'Verify your FDS account'
            html_message = render_to_string('dev_productivity/auth/verification_email.html', {
                'user': user,
                'verification_url': verification_url,
                'site_name': 'FDS Analyzer'
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False
            )
            
            messages.success(request, f'Verification email sent to {email}')
            
        except User.DoesNotExist:
            messages.error(request, 'No unverified account found with this email address.')
        except Exception as e:
            logger.error(f"Failed to resend verification email: {e}")
            messages.error(request, 'Failed to send verification email. Please try again.')
    
    return render(request, 'dev_productivity/auth/resend_verification.html')


def password_reset_request(request):
    """Password reset request view"""
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            
            try:
                user = User.objects.get(email=email, is_active=True)
                
                # Create reset token
                token = str(uuid.uuid4())
                expires_at = timezone.now() + timedelta(hours=24)
                
                PasswordResetToken.objects.create(
                    user=user,
                    token=token,
                    expires_at=expires_at
                )
                
                # Send reset email
                reset_url = request.build_absolute_uri(
                    reverse('password_reset_confirm', kwargs={'token': token})
                )
                
                subject = 'Reset your FDS password'
                html_message = render_to_string('dev_productivity/auth/password_reset_email.html', {
                    'user': user,
                    'reset_url': reset_url,
                    'site_name': 'FDS Analyzer'
                })
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False
                )
                
                messages.success(
                    request,
                    f'Password reset instructions have been sent to {email}'
                )
                
            except User.DoesNotExist:
                # Don't reveal if email exists
                messages.success(
                    request,
                    f'If an account with {email} exists, password reset instructions have been sent.'
                )
            except Exception as e:
                logger.error(f"Failed to send password reset email: {e}")
                messages.error(request, 'Failed to send password reset email. Please try again.')
    else:
        form = CustomPasswordResetForm()
    
    return render(request, 'dev_productivity/auth/password_reset.html', {'form': form})


def password_reset_confirm(request, token):
    """Password reset confirmation view"""
    try:
        reset_token = get_object_or_404(PasswordResetToken, token=token, used=False)
        
        if reset_token.is_expired():
            messages.error(request, 'Password reset link has expired. Please request a new one.')
            return redirect('password_reset')
        
        if request.method == 'POST':
            form = CustomSetPasswordForm(reset_token.user, request.POST)
            if form.is_valid():
                form.save()
                
                # Mark token as used
                reset_token.used = True
                reset_token.save()
                
                messages.success(request, 'Password reset successfully! You can now log in.')
                return redirect('login')
        else:
            form = CustomSetPasswordForm(reset_token.user)
        
        return render(request, 'dev_productivity/auth/password_reset_confirm.html', {
            'form': form,
            'token': token
        })
        
    except Exception as e:
        logger.error(f"Password reset confirmation failed for token {token}: {e}")
        messages.error(request, 'Invalid or expired password reset link.')
        return redirect('password_reset')


@login_required
def user_dashboard(request):
    """User dashboard view"""
    user = request.user
    
    # Get user's analyses
    recent_analyses = user.analyses.all()[:5]
    total_analyses = user.analyses.count()
    completed_analyses = user.analyses.filter(status='completed').count()
    running_analyses = user.analyses.filter(status='running').count()
    
    # Get recent activity
    recent_activity = user.activity_logs.all()[:10]
    
    # Calculate success rate
    success_rate = (completed_analyses / total_analyses * 100) if total_analyses > 0 else 0
    
    context = {
        'user': user,
        'recent_analyses': recent_analyses,
        'total_analyses': total_analyses,
        'completed_analyses': completed_analyses,
        'running_analyses': running_analyses,
        'success_rate': success_rate,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'dev_productivity/auth/dashboard.html', context)


@login_required
def user_profile(request):
    """User profile view"""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            log_user_activity(request.user, 'profile_update', 'Profile updated', request)
            return redirect('user_profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'dev_productivity/auth/profile.html', {'form': form})


@login_required
def user_settings(request):
    """User settings view"""
    user = request.user
    
    # Get or create preferences
    from .models import UserPreference
    preferences, created = UserPreference.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=user)
        token_form = GitHubTokenForm(request.POST)
        preferences_form = UserPreferencesForm(request.POST, instance=preferences) if preferences else None
        
        if profile_form.is_valid() and token_form.is_valid():
            # Save profile
            profile_form.save()
            
            # Save GitHub token
            github_token = token_form.cleaned_data.get('github_access_token')
            if github_token:
                user.github_access_token = github_token
                user.save(update_fields=['github_access_token'])
                log_user_activity(user, 'token_update', 'GitHub token updated', request)
            
            # Save preferences
            if preferences_form and preferences_form.is_valid():
                preferences_form.save()
            
            messages.success(request, 'Settings updated successfully!')
            log_user_activity(user, 'settings_update', 'Settings updated', request)
            
            return redirect('user_settings')
    else:
        profile_form = UserProfileForm(instance=user)
        token_form = GitHubTokenForm()
        preferences_form = UserPreferencesForm(instance=preferences) if preferences else None
    
    context = {
        'profile_form': profile_form,
        'token_form': token_form,
        'preferences_form': preferences_form,
        'user': user,
    }
    
    return render(request, 'dev_productivity/auth/settings.html', context)


@login_required
def user_analyses(request):
    """User's analyses list view"""
    user = request.user
    analyses = user.analyses.all()
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter and status_filter in ['pending', 'running', 'completed', 'failed']:
        analyses = analyses.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        analyses = analyses.filter(repo_url__icontains=search_query)
    
    context = {
        'analyses': analyses,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'dev_productivity/auth/user_analyses.html', context)


@login_required
def delete_account(request):
    """Delete user account view"""
    if request.method == 'POST':
        password = request.POST.get('password')
        
        if request.user.check_password(password):
            user = request.user
            
            # Log activity before deletion
            log_user_activity(user, 'account_delete', 'Account deleted', request)
            
            # Delete user (will cascade to analyses)
            user.delete()
            
            messages.success(request, 'Your account has been deleted successfully.')
            return redirect('home')
        else:
            messages.error(request, 'Incorrect password. Account not deleted.')
    
    return render(request, 'dev_productivity/auth/delete_account.html')


@login_required
@require_GET
def activity_log(request):
    """User activity log view"""
    activities = request.user.activity_logs.all()[:50]
    return render(request, 'dev_productivity/auth/activity_log.html', {'activities': activities})


@login_required
@require_POST
def clear_github_token(request):
    """Clear user's GitHub token"""
    request.user.github_access_token = ''
    request.user.save(update_fields=['github_access_token'])
    
    log_user_activity(request.user, 'token_clear', 'GitHub token cleared', request)
    messages.success(request, 'GitHub token cleared successfully.')
    
    return redirect('user_settings')
