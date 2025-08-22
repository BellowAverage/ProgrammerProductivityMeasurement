from django.utils import timezone
from django.http import HttpRequest
from .models import ActivityLog
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_user_activity(user, action, description='', request=None, analysis=None, metadata=None):
    """Log user activity"""
    try:
        activity_data = {
            'user': user,
            'action': action,
            'description': description,
        }
        
        if request:
            activity_data.update({
                'ip_address': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            })
        
        if analysis:
            activity_data['analysis'] = analysis
        
        if metadata:
            activity_data['metadata'] = metadata
        
        ActivityLog.objects.create(**activity_data)
        
    except Exception as e:
        logger.error(f"Failed to log user activity: {e}")


def get_user_preferences(user):
    """Get user preferences with defaults"""
    if hasattr(user, 'preferences'):
        return user.preferences
    
    # Create default preferences if they don't exist
    from .models import UserPreference
    preferences, created = UserPreference.objects.get_or_create(user=user)
    return preferences


def format_file_size(bytes_size):
    """Format file size in human readable format"""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"


def get_analysis_summary(analysis):
    """Get summary statistics for an analysis"""
    summary = {
        'total_commits': analysis.total_commits or 0,
        'total_developers': analysis.total_developers or 0,
        'total_batches': analysis.total_batches or 0,
        'execution_time': analysis.execution_time or 0,
        'status': analysis.status,
    }
    
    if analysis.status == 'completed':
        # Add developer scores summary
        developer_scores = analysis.developer_scores.all()
        if developer_scores:
            scores = [score.fds_score for score in developer_scores]
            summary.update({
                'avg_fds_score': sum(scores) / len(scores),
                'max_fds_score': max(scores),
                'min_fds_score': min(scores),
            })
    
    return summary


def send_notification_email(user, subject, template, context):
    """Send notification email to user"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.conf import settings
    
    if not user.email_notifications:
        return False
    
    try:
        html_message = render_to_string(template, context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send notification email to {user.email}: {e}")
        return False


def cleanup_expired_tokens():
    """Cleanup expired tokens (run as periodic task)"""
    from .models import EmailVerificationToken, PasswordResetToken
    
    now = timezone.now()
    
    # Delete expired email verification tokens
    expired_email_tokens = EmailVerificationToken.objects.filter(expires_at__lt=now)
    email_count = expired_email_tokens.count()
    expired_email_tokens.delete()
    
    # Delete expired password reset tokens
    expired_reset_tokens = PasswordResetToken.objects.filter(expires_at__lt=now)
    reset_count = expired_reset_tokens.count()
    expired_reset_tokens.delete()
    
    logger.info(f"Cleaned up {email_count} expired email tokens and {reset_count} expired reset tokens")
    
    return email_count + reset_count


def get_user_storage_usage(user):
    """Calculate user's storage usage"""
    import os
    
    user_folder = user.get_user_folder()
    total_size = 0
    
    try:
        for dirpath, dirnames, filenames in os.walk(user_folder):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except Exception as e:
        logger.error(f"Failed to calculate storage usage for user {user.id}: {e}")
    
    return total_size


def cleanup_user_data(user, days_to_keep=365):
    """Cleanup old user analysis data"""
    import shutil
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    old_analyses = user.analyses.filter(created_at__lt=cutoff_date, status='completed')
    
    deleted_count = 0
    for analysis in old_analyses:
        try:
            analysis_folder = analysis.get_analysis_folder()
            if analysis_folder.exists():
                shutil.rmtree(analysis_folder)
            analysis.delete()
            deleted_count += 1
        except Exception as e:
            logger.error(f"Failed to cleanup analysis {analysis.id}: {e}")
    
    return deleted_count
