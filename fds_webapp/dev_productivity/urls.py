from django.urls import path
from . import views, auth_views

urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    path('analyses/', views.analysis_list, name='analysis_list'),
    path('analysis/<int:analysis_id>/', views.analysis_detail, name='analysis_detail'),
    path('analysis/<int:analysis_id>/status/', views.analysis_status, name='analysis_status'),
    path('analysis/<int:analysis_id>/developer/<str:developer_email>/', views.developer_detail, name='developer_detail'),
    path('analysis/<int:analysis_id>/batch/<int:batch_id>/', views.batch_detail, name='batch_detail'),
    
    # Authentication URLs
    path('auth/register/', auth_views.register_view, name='register'),
    path('auth/login/', auth_views.login_view, name='login'),
    path('auth/logout/', auth_views.logout_view, name='logout'),
    path('auth/verify-email/<str:token>/', auth_views.verify_email, name='verify_email'),
    path('auth/resend-verification/', auth_views.resend_verification, name='resend_verification'),
    path('auth/password-reset/', auth_views.password_reset_request, name='password_reset'),
    path('auth/password-reset/confirm/<str:token>/', auth_views.password_reset_confirm, name='password_reset_confirm'),
    
    # User dashboard and management
    path('dashboard/', auth_views.user_dashboard, name='user_dashboard'),
    path('profile/', auth_views.user_profile, name='user_profile'),
    path('settings/', auth_views.user_settings, name='user_settings'),
    path('analyses/my/', auth_views.user_analyses, name='user_analyses'),
    path('activity/', auth_views.activity_log, name='activity_log'),
    path('delete-account/', auth_views.delete_account, name='delete_account'),
    
    # Analysis management (authenticated users)
    path('create-analysis/', views.create_analysis, name='create_analysis'),
    path('analysis/<int:analysis_id>/delete/', views.delete_analysis, name='delete_analysis'),
    path('analysis/<int:analysis_id>/share/', views.share_analysis, name='share_analysis'),
    path('analysis/<int:analysis_id>/toggle-privacy/', views.toggle_analysis_privacy, name='toggle_analysis_privacy'),
    
    # Compare route kept for backward compatibility; view redirects to overview
    path('analysis/<int:analysis_id>/compare/', views.compare_developers, name='compare_developers'),
    
    # Frontend dashboard and data API
    path('analysis/<int:analysis_id>/dashboard/', views.dashboard, name='dashboard'),
    path('analysis/<int:analysis_id>/dashboard/data/', views.dashboard_data, name='dashboard_data'),
    path('analysis/<int:analysis_id>/download/csvs/', views.download_analysis_csvs, name='download_analysis_csvs'),
    
    # Tools and utilities
    path('tools/settings/', views.settings_page, name='settings'),
    path('tools/test-runner/', views.test_runner_page, name='test_runner'),
    path('auth/clear-github-token/', auth_views.clear_github_token, name='clear_github_token'),
]