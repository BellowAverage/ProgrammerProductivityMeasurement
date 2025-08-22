from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import authenticate
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import FDSAnalysis, User, UserPreference
import re


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form with minimal requirements"""
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address (optional)',
            'autocomplete': 'email'
        })
    )
    
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name (optional)',
            'autocomplete': 'given-name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name (optional)',
            'autocomplete': 'family-name'
        })
    )
    
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a username',
            'autocomplete': 'username'
        }),
        help_text="Required. Letters, digits and @/./+/-/_ only."
    )
    
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password',
            'autocomplete': 'new-password'
        }),
        help_text="Required. Any password is acceptable."
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        })
    )
    
    organization = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your organization (optional)',
            'autocomplete': 'organization'
        })
    )
    
    job_title = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your job title (optional)',
            'autocomplete': 'organization-title'
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I agree to the Terms of Service and Privacy Policy (optional)"
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'organization', 'job_title', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip()
            if User.objects.filter(email=email).exists():
                raise ValidationError("A user with this email address already exists.")
        return email or ''
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '') or ''
        user.first_name = self.cleaned_data.get('first_name', '') or ''
        user.last_name = self.cleaned_data.get('last_name', '') or ''
        user.organization = self.cleaned_data.get('organization', '') or ''
        user.job_title = self.cleaned_data.get('job_title', '') or ''
        user.is_active = True
        user.email_verified = True if not user.email else False  # Auto-verify if no email provided
        
        if commit:
            user.save()
            # Create user preferences
            UserPreference.objects.create(user=user)
        
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with email or username"""
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email or username',
            'autocomplete': 'username'
        }),
        label="Email or Username"
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'autocomplete': 'current-password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Remember me"
    )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Check if it's an email
            if '@' in username:
                try:
                    validate_email(username)
                    # Try to find user by email
                    try:
                        user = User.objects.get(email=username)
                        return user.username
                    except User.DoesNotExist:
                        pass
                except ValidationError:
                    pass
        return username


class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email'
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    """Custom set password form"""
    
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password',
            'autocomplete': 'new-password'
        })
    )
    
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password'
        })
    )


class FDSAnalysisForm(forms.ModelForm):
    """Form for creating FDS analysis"""
    
    repo_url = forms.URLField(
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://github.com/owner/repository',
            'pattern': r'https://github\.com/[^/]+/[^/]+/?'
        }),
        help_text="Enter the GitHub repository URL (e.g., https://github.com/facebook/react)"
    )
    
    commit_limit = forms.IntegerField(
        min_value=10,
        max_value=5000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '300'
        }),
        help_text="Number of recent commits to analyze (10-5000)"
    )
    
    use_personal_token = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Use my personal GitHub token",
        help_text="Use your saved GitHub token for higher API limits"
    )
    
    access_token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }),
        help_text="GitHub personal access token (optional, overrides personal token)"
    )
    
    is_public = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Make analysis results public",
        help_text="Allow other users to view this analysis"
    )
    
    class Meta:
        model = FDSAnalysis
        fields = ['repo_url', 'commit_limit', 'access_token', 'is_public']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default values from user preferences
        if self.user:
            self.fields['commit_limit'].initial = self.user.default_commit_limit
            if hasattr(self.user, 'preferences'):
                self.fields['is_public'].initial = self.user.preferences.default_repo_privacy
    
    def clean_repo_url(self):
        url = self.cleaned_data.get('repo_url')
        if url:
            # Validate GitHub URL format
            github_pattern = re.compile(r'https://github\.com/([^/]+)/([^/]+)/?$')
            if not github_pattern.match(url):
                raise ValidationError("Please enter a valid GitHub repository URL")
        return url
    
    def clean_access_token(self):
        token = self.cleaned_data.get('access_token')
        use_personal = self.cleaned_data.get('use_personal_token', False)
        
        if not token and not use_personal:
            if self.user and self.user.github_access_token:
                # Use user's personal token
                return self.user.github_access_token
            else:
                raise ValidationError("GitHub access token is required. Please provide a token or save one in your settings.")
        
        if token and not token.startswith('ghp_'):
            raise ValidationError("Invalid GitHub token format. Token should start with 'ghp_'")
        
        return token
    
    def save(self, commit=True):
        analysis = super().save(commit=False)
        if self.user:
            analysis.user = self.user
            
            # Use personal token if requested
            if self.cleaned_data.get('use_personal_token') and self.user.github_access_token:
                analysis.access_token = self.user.github_access_token
        
        if commit:
            analysis.save()
        
        return analysis


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile"""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'github_username', 
                  'organization', 'job_title', 'default_commit_limit']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'github_username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your GitHub username'}),
            'organization': forms.TextInput(attrs={'class': 'form-control'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control'}),
            'default_commit_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': '10', 'max': '5000'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A user with this email address already exists.")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A user with this username already exists.")
        return username


class GitHubTokenForm(forms.Form):
    """Form for managing GitHub access token"""
    
    github_access_token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }),
        help_text="Your GitHub personal access token for API access"
    )
    
    def clean_github_access_token(self):
        token = self.cleaned_data.get('github_access_token')
        if token and not token.startswith('ghp_'):
            raise ValidationError("Invalid GitHub token format. Token should start with 'ghp_'")
        return token


class UserPreferencesForm(forms.ModelForm):
    """Form for user preferences and settings"""
    
    class Meta:
        model = UserPreference
        fields = [
            'default_repo_privacy', 'auto_share_with_team', 'theme', 'items_per_page',
            'dashboard_layout', 'email_on_completion', 'email_on_failure', 
            'email_weekly_summary', 'auto_delete_failed', 'keep_analysis_data_days'
        ]
        widgets = {
            'default_repo_privacy': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_share_with_team': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'theme': forms.Select(attrs={'class': 'form-select'}),
            'items_per_page': forms.Select(attrs={'class': 'form-select'}),
            'dashboard_layout': forms.Select(attrs={'class': 'form-select'}),
            'email_on_completion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_on_failure': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_weekly_summary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_delete_failed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'keep_analysis_data_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '3650'}),
        }


class AnalysisSharingForm(forms.Form):
    """Form for sharing analysis with other users"""
    
    email_addresses = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter email addresses, one per line'
        }),
        help_text="Enter email addresses of users to share this analysis with"
    )
    
    def clean_email_addresses(self):
        emails_text = self.cleaned_data.get('email_addresses', '')
        emails = [email.strip() for email in emails_text.split('\n') if email.strip()]
        
        valid_emails = []
        for email in emails:
            try:
                validate_email(email)
                valid_emails.append(email)
            except ValidationError:
                raise ValidationError(f"Invalid email address: {email}")
        
        return valid_emails