from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, FDSAnalysis, DeveloperScore, BatchMetrics, 
    UserPreference, ActivityLog, EmailVerificationToken, 
    PasswordResetToken, UserSession
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'first_name', 'last_name', 'is_active', 'email_verified', 'created_at']
    list_filter = ['is_active', 'email_verified', 'is_staff', 'is_superuser', 'created_at']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'organization']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Profile', {'fields': ('github_username', 'organization', 'job_title')}),
        ('Preferences', {'fields': ('default_commit_limit', 'email_notifications', 'analysis_notifications')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
        ('Security', {'fields': ('email_verified', 'last_login_ip')}),
        ('GitHub Integration', {'fields': ('github_access_token',)}),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login']
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    def get_analyses_count(self, obj):
        return obj.analyses.count()
    get_analyses_count.short_description = 'Analyses'
    
    def get_completed_analyses(self, obj):
        return obj.analyses.filter(status='completed').count()
    get_completed_analyses.short_description = 'Completed'


@admin.register(FDSAnalysis)
class FDSAnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_link', 'repo_name', 'status', 'total_commits', 'total_developers', 'is_public', 'created_at']
    list_filter = ['status', 'is_public', 'created_at', 'user']
    search_fields = ['repo_url', 'user__email', 'user__username']
    readonly_fields = ['created_at', 'started_at', 'completed_at', 'execution_time']
    
    fieldsets = (
        ('Owner', {
            'fields': ('user',)
        }),
        ('Repository Info', {
            'fields': ('repo_url', 'access_token', 'commit_limit')
        }),
        ('Privacy', {
            'fields': ('is_public', 'shared_with')
        }),
        ('Analysis Status', {
            'fields': ('status', 'error_message')
        }),
        ('Results', {
            'fields': ('total_commits', 'total_batches', 'total_developers', 'execution_time')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at')
        }),
    )
    
    def user_link(self, obj):
        return format_html('<a href="/admin/dev_productivity/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
    user_link.short_description = 'User'
    
    def repo_name(self, obj):
        return obj.get_repo_name()
    repo_name.short_description = 'Repository'


@admin.register(DeveloperScore)
class DeveloperScoreAdmin(admin.ModelAdmin):
    list_display = ['author_email', 'analysis', 'fds_score', 'total_commits', 'unique_batches']
    list_filter = ['analysis']
    search_fields = ['author_email']
    ordering = ['-fds_score']


@admin.register(BatchMetrics)
class BatchMetricsAdmin(admin.ModelAdmin):
    list_display = ['batch_id', 'analysis', 'unique_authors', 'commit_count', 'total_contribution']
    list_filter = ['analysis', 'unique_authors']
    ordering = ['-total_contribution']


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'items_per_page', 'email_on_completion', 'created_at']
    list_filter = ['theme', 'email_on_completion', 'email_on_failure']
    search_fields = ['user__email', 'user__username']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'description', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email', 'description', 'ip_address']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        return False  # Activity logs are created automatically


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'token_preview', 'created_at', 'expires_at', 'is_expired_status']
    list_filter = ['created_at', 'expires_at']
    search_fields = ['user__email']
    readonly_fields = ['created_at', 'is_expired_status']
    
    def token_preview(self, obj):
        return f"{obj.token[:8]}..."
    token_preview.short_description = 'Token'
    
    def is_expired_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Valid</span>')
    is_expired_status.short_description = 'Status'


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'token_preview', 'created_at', 'expires_at', 'used', 'is_expired_status']
    list_filter = ['used', 'created_at', 'expires_at']
    search_fields = ['user__email']
    readonly_fields = ['created_at', 'is_expired_status']
    
    def token_preview(self, obj):
        return f"{obj.token[:8]}..."
    token_preview.short_description = 'Token'
    
    def is_expired_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Valid</span>')
    is_expired_status.short_description = 'Status'


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'session_preview', 'created_at', 'last_activity']
    list_filter = ['created_at', 'last_activity']
    search_fields = ['user__email', 'ip_address']
    readonly_fields = ['created_at', 'last_activity']
    ordering = ['-last_activity']
    
    def session_preview(self, obj):
        return f"{obj.session_key[:8]}..."
    session_preview.short_description = 'Session'