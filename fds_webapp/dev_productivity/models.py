from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.validators import EmailValidator
import json
import os
from pathlib import Path
from django.conf import settings


class User(AbstractUser):
    """Extended User model with additional fields for FDS application"""
    email = models.EmailField(blank=True, null=True, validators=[EmailValidator()])
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    
    # Profile fields
    github_username = models.CharField(max_length=100, blank=True, null=True)
    github_access_token = models.CharField(max_length=200, blank=True, null=True, help_text="Personal GitHub access token")
    organization = models.CharField(max_length=200, blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, null=True)
    
    # Preferences
    default_commit_limit = models.IntegerField(default=300, help_text="Default number of commits to analyze")
    email_notifications = models.BooleanField(default=True)
    analysis_notifications = models.BooleanField(default=True)
    
    # Account status
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'auth_user'
        
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_user_folder(self):
        """Get the user's personal analysis folder"""
        user_folder = Path(settings.MEDIA_ROOT) / 'user_analyses' / f'user_{self.id}'
        user_folder.mkdir(parents=True, exist_ok=True)
        return user_folder
    
    def get_analyses_count(self):
        """Get count of user's analyses"""
        return self.analyses.count()
    
    def get_completed_analyses_count(self):
        """Get count of user's completed analyses"""
        return self.analyses.filter(status='completed').count()


class EmailVerificationToken(models.Model):
    """Email verification tokens for user registration"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"Verification token for {self.user.email}"


class PasswordResetToken(models.Model):
    """Password reset tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"Password reset token for {self.user.email}"


class UserSession(models.Model):
    """Track user sessions and preferences"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(default=timezone.now)
    
    # Cached preferences
    preferences = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"Session for {self.user.email} from {self.ip_address}"


class FDSAnalysis(models.Model):
    """Model to store FDS analysis jobs and results"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Link to user
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    
    # Input parameters
    repo_url = models.URLField(max_length=500, help_text="GitHub repository URL")
    access_token = models.CharField(max_length=200, help_text="GitHub access token", blank=True)
    commit_limit = models.IntegerField(default=300, help_text="Number of commits to analyze")
    
    # Analysis metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results summary
    total_commits = models.IntegerField(null=True, blank=True)
    total_batches = models.IntegerField(null=True, blank=True)
    total_developers = models.IntegerField(null=True, blank=True)
    execution_time = models.FloatField(null=True, blank=True, help_text="Execution time in seconds")
    
    # Error handling
    error_message = models.TextField(blank=True, null=True)
    
    # Privacy settings
    is_public = models.BooleanField(default=False, help_text="Make analysis results publicly viewable")
    shared_with = models.ManyToManyField(User, blank=True, related_name='shared_analyses')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "FDS Analysis"
        verbose_name_plural = "FDS Analyses"
    
    def __str__(self):
        return f"FDS Analysis for {self.repo_url} by {self.user.email} ({self.status})"
    
    def get_repo_name(self):
        """Extract repository name from URL"""
        if self.repo_url:
            return self.repo_url.rstrip('/').split('/')[-1]
        return "Unknown Repository"
    
    def get_owner_repo(self):
        """Extract owner/repo from URL"""
        if self.repo_url:
            parts = self.repo_url.rstrip('/').split('/')
            if len(parts) >= 2:
                return f"{parts[-2]}/{parts[-1]}"
        return "Unknown"
    
    def get_analysis_folder(self):
        """Get the folder for this specific analysis"""
        user_folder = self.user.get_user_folder()
        analysis_folder = user_folder / f'analysis_{self.id}_{self.get_repo_name()}'
        analysis_folder.mkdir(parents=True, exist_ok=True)
        return analysis_folder
    
    def can_view(self, user):
        """Check if user can view this analysis"""
        if not user.is_authenticated:
            return self.is_public
        if self.user == user:
            return True
        if self.is_public:
            return True
        if user in self.shared_with.all():
            return True
        return False


class DeveloperScore(models.Model):
    """Model to store individual developer FDS scores"""
    
    analysis = models.ForeignKey(FDSAnalysis, on_delete=models.CASCADE, related_name='developer_scores')
    
    # Developer info
    author_email = models.EmailField()
    fds_score = models.FloatField(help_text="Fair Developer Score")
    
    # Aggregated metrics
    avg_effort = models.FloatField(default=0.0)
    avg_importance = models.FloatField(default=0.0)
    total_commits = models.IntegerField(default=0)
    unique_batches = models.IntegerField(default=0)
    total_churn = models.IntegerField(default=0)
    total_files = models.IntegerField(default=0)
    
    # Effort components (normalized)
    share_mean = models.FloatField(default=0.0)
    scale_z_mean = models.FloatField(default=0.0)
    reach_z_mean = models.FloatField(default=0.0)
    centrality_z_mean = models.FloatField(default=0.0)
    dominance_z_mean = models.FloatField(default=0.0)
    novelty_z_mean = models.FloatField(default=0.0)
    speed_z_mean = models.FloatField(default=0.0)
    
    # Activity metrics
    first_commit_date = models.DateTimeField(null=True, blank=True)
    last_commit_date = models.DateTimeField(null=True, blank=True)
    activity_span_days = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-fds_score']
        unique_together = ['analysis', 'author_email']
    
    def __str__(self):
        return f"{self.author_email}: {self.fds_score:.2f}"


class BatchMetrics(models.Model):
    """Model to store batch-level collaboration data"""
    
    analysis = models.ForeignKey(FDSAnalysis, on_delete=models.CASCADE, related_name='batch_metrics')
    
    # Batch identification
    batch_id = models.IntegerField()
    
    # Collaboration metrics
    unique_authors = models.IntegerField(default=0)
    total_contribution = models.FloatField(default=0.0)
    avg_contribution = models.FloatField(default=0.0)
    max_contribution = models.FloatField(default=0.0)
    
    # Batch characteristics
    avg_effort = models.FloatField(default=0.0)
    importance = models.FloatField(default=0.0)
    total_churn = models.IntegerField(default=0)
    total_files = models.IntegerField(default=0)
    commit_count = models.IntegerField(default=0)
    
    # Temporal data
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration_hours = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-importance']
        unique_together = ['analysis', 'batch_id']
    
    def __str__(self):
        return f"Batch {self.batch_id} (Analysis {self.analysis.id})"


class UserPreference(models.Model):
    """Store user preferences and settings"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    
    # Analysis preferences
    default_repo_privacy = models.BooleanField(default=False, help_text="Make analyses public by default")
    auto_share_with_team = models.BooleanField(default=False)
    
    # UI preferences
    theme = models.CharField(max_length=20, choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')], default='light')
    items_per_page = models.IntegerField(default=20, choices=[(10, '10'), (20, '20'), (50, '50'), (100, '100')])
    dashboard_layout = models.CharField(max_length=20, choices=[('grid', 'Grid'), ('list', 'List')], default='grid')
    
    # Notification preferences
    email_on_completion = models.BooleanField(default=True)
    email_on_failure = models.BooleanField(default=True)
    email_weekly_summary = models.BooleanField(default=False)
    
    # Data retention preferences
    auto_delete_failed = models.BooleanField(default=False, help_text="Auto-delete failed analyses after 30 days")
    keep_analysis_data_days = models.IntegerField(default=365, help_text="Days to keep analysis data")
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.email}"


class ActivityLog(models.Model):
    """Log user activities for audit and analytics"""
    
    ACTION_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('analysis_create', 'Analysis Created'),
        ('analysis_view', 'Analysis Viewed'),
        ('analysis_delete', 'Analysis Deleted'),
        ('analysis_share', 'Analysis Shared'),
        ('settings_update', 'Settings Updated'),
        ('token_update', 'GitHub Token Updated'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    # Related objects
    analysis = models.ForeignKey(FDSAnalysis, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email}: {self.get_action_display()} at {self.created_at}"