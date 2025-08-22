from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from dev_productivity.models import FDSAnalysis

User = get_user_model()


class Command(BaseCommand):
    help = 'List all registered users with their analysis statistics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed user information',
        )

    def handle(self, *args, **options):
        users = User.objects.all().order_by('-created_at')
        
        if not users.exists():
            self.stdout.write(self.style.WARNING('No users found in the database.'))
            return
        
        self.stdout.write(f'\n=== REGISTERED USERS ({users.count()}) ===\n')
        
        for user in users:
            # Basic info
            self.stdout.write(f'🔹 ID: {user.id}')
            self.stdout.write(f'   Email: {user.email}')
            self.stdout.write(f'   Name: {user.get_full_name()}')
            self.stdout.write(f'   Username: {user.username}')
            self.stdout.write(f'   Active: {"✅" if user.is_active else "❌"}')
            self.stdout.write(f'   Email Verified: {"✅" if user.email_verified else "❌"}')
            self.stdout.write(f'   Created: {user.created_at.strftime("%Y-%m-%d %H:%M")}')
            
            if options['detailed']:
                # Additional details
                self.stdout.write(f'   Organization: {user.organization or "Not specified"}')
                self.stdout.write(f'   Job Title: {user.job_title or "Not specified"}')
                self.stdout.write(f'   GitHub Username: {user.github_username or "Not specified"}')
                self.stdout.write(f'   GitHub Token: {"✅ Configured" if user.github_access_token else "❌ Not configured"}')
                self.stdout.write(f'   Last Login: {user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Never"}')
                self.stdout.write(f'   Last Login IP: {user.last_login_ip or "Unknown"}')
            
            # Analysis statistics
            total_analyses = user.analyses.count()
            completed_analyses = user.analyses.filter(status='completed').count()
            running_analyses = user.analyses.filter(status='running').count()
            failed_analyses = user.analyses.filter(status='failed').count()
            
            self.stdout.write(f'   Analyses: {total_analyses} total, {completed_analyses} completed, {running_analyses} running, {failed_analyses} failed')
            
            if options['detailed'] and total_analyses > 0:
                self.stdout.write('   Recent analyses:')
                for analysis in user.analyses.all()[:3]:
                    self.stdout.write(f'     - {analysis.get_repo_name()} ({analysis.status}) - {analysis.created_at.strftime("%Y-%m-%d")}')
            
            self.stdout.write('')  # Empty line
        
        # Summary statistics
        self.stdout.write('=== SUMMARY ===')
        self.stdout.write(f'Total users: {users.count()}')
        self.stdout.write(f'Active users: {users.filter(is_active=True).count()}')
        self.stdout.write(f'Verified emails: {users.filter(email_verified=True).count()}')
        self.stdout.write(f'Users with GitHub tokens: {users.exclude(github_access_token="").exclude(github_access_token__isnull=True).count()}')
        
        total_analyses = FDSAnalysis.objects.count()
        self.stdout.write(f'Total analyses: {total_analyses}')
        self.stdout.write(f'Public analyses: {FDSAnalysis.objects.filter(is_public=True).count()}')
        
        self.stdout.write('\n✅ Use --detailed flag for more information')
        self.stdout.write('✅ Access Django admin at: http://127.0.0.1:8007/admin/')
        self.stdout.write('✅ Users should be visible under "DEV_PRODUCTIVITY" → "Users"')

