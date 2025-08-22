from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import models
from django.core.exceptions import PermissionDenied
from .models import FDSAnalysis, DeveloperScore, BatchMetrics, User
from .forms import FDSAnalysisForm, AnalysisSharingForm
from .services import FDSAnalysisService
from .utils import log_user_activity, get_user_preferences
import json
from django.utils.safestring import mark_safe
from pathlib import Path
import io
import zipfile
import pandas as pd
import math


def home(request):
    """Home page - redirect authenticated users to dashboard"""
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    
    # Show public analyses for anonymous users
    public_analyses = FDSAnalysis.objects.filter(is_public=True, status='completed')[:5]
    
    context = {
        'public_analyses': public_analyses,
    }
    return render(request, 'dev_productivity/home.html', context)


@login_required
def create_analysis(request):
    """Create new analysis (authenticated users only)"""
    if request.method == 'POST':
        form = FDSAnalysisForm(request.POST, user=request.user)
        if form.is_valid():
            analysis = form.save()
            
            # Start analysis in background
            service = FDSAnalysisService()
            service.start_analysis(analysis.id)
            
            # Log activity
            log_user_activity(
                request.user, 
                'analysis_create', 
                f'Created analysis for {analysis.repo_url}', 
                request, 
                analysis
            )
            
            messages.success(request, f'Analysis started for {analysis.get_repo_name()}. Analysis ID: {analysis.id}')
            return redirect('analysis_detail', analysis_id=analysis.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = FDSAnalysisForm(user=request.user)
    
    return render(request, 'dev_productivity/create_analysis.html', {'form': form})


def analysis_list(request):
    """List public analyses for all users, or user's analyses if authenticated"""
    if request.user.is_authenticated:
        # Show user's own analyses and public analyses
        analyses = FDSAnalysis.objects.filter(
            models.Q(user=request.user) | models.Q(is_public=True)
        ).distinct()
    else:
        # Show only public analyses
        analyses = FDSAnalysis.objects.filter(is_public=True)
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter and status_filter in ['pending', 'running', 'completed', 'failed']:
        analyses = analyses.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        analyses = analyses.filter(repo_url__icontains=search_query)
    
    paginator = Paginator(analyses, 20)  # Show 20 analyses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary statistics
    total_analyses = analyses.count()
    completed_analyses = analyses.filter(status='completed').count()
    success_rate = (completed_analyses / total_analyses * 100) if total_analyses > 0 else 0
    
    # Calculate average duration for completed analyses
    completed_with_time = analyses.filter(status='completed', execution_time__isnull=False)
    avg_duration = completed_with_time.aggregate(models.Avg('execution_time'))['execution_time__avg'] or 0
    
    # Calculate total commits
    total_commits = analyses.filter(total_commits__isnull=False).aggregate(models.Sum('total_commits'))['total_commits__sum'] or 0
    
    context = {
        'page_obj': page_obj,
        'total_analyses': total_analyses,
        'success_rate': success_rate,
        'avg_duration': avg_duration,
        'total_commits': total_commits,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'dev_productivity/analysis_list.html', context)


def analysis_detail(request, analysis_id):
    """Show detailed results of an analysis"""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    
    # Check permissions
    if not analysis.can_view(request.user):
        raise PermissionDenied("You don't have permission to view this analysis.")

    # Log activity for authenticated users
    if request.user.is_authenticated:
        log_user_activity(
            request.user,
            'analysis_view',
            f'Viewed analysis {analysis.id}',
            request,
            analysis
        )

    # Auto-backfill developer scores from saved artifacts if they are missing
    if analysis.status == 'completed' and analysis.developer_scores.count() == 0:
        _try_backfill_developer_scores(analysis)

    # Get developer scores with pagination
    developer_scores = analysis.developer_scores.all()
    dev_paginator = Paginator(developer_scores, 20)
    dev_page = request.GET.get('dev_page')
    dev_page_obj = dev_paginator.get_page(dev_page)
    
    # Get top batches
    top_batches = analysis.batch_metrics.all()[:10]
    
    # Calculate statistics
    stats = {}
    if analysis.status == 'completed':
        scores = list(developer_scores.values_list('fds_score', flat=True))
        if scores:
            stats = {
                'total_fds': sum(scores),
                'avg_fds': sum(scores) / len(scores),
                'max_fds': max(scores),
                'min_fds': min(scores),
            }
    
    # Check if user can edit this analysis
    can_edit = request.user.is_authenticated and analysis.user == request.user
    
    context = {
        'analysis': analysis,
        'dev_page_obj': dev_page_obj,
        'top_batches': top_batches,
        'stats': stats,
        'can_edit': can_edit,
    }
    return render(request, 'dev_productivity/analysis_detail.html', context)


def analysis_status(request, analysis_id):
    """API endpoint to check analysis status"""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    
    data = {
        'status': analysis.status,
        'total_commits': analysis.total_commits,
        'total_batches': analysis.total_batches,
        'total_developers': analysis.total_developers,
        'execution_time': analysis.execution_time,
        'error_message': analysis.error_message,
    }
    
    if analysis.completed_at:
        data['completed_at'] = analysis.completed_at.isoformat()
    
    return JsonResponse(data)


def developer_detail(request, analysis_id, developer_email):
    """Show detailed metrics for a specific developer (with per-build contributions)."""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    developer = get_object_or_404(
        DeveloperScore,
        analysis=analysis,
        author_email=developer_email,
    )

    # Build artifact path
    folder = _get_artifacts_folder(analysis)

    # Gather per-build contributions for this developer from artifacts, fallback to DB
    top_build_rows = []
    try:
        contrib_csv = folder / 'individual_contributions.csv'
        if contrib_csv.exists():
            df = pd.read_csv(contrib_csv)
            if 'author_email' in df.columns and 'batch_id' in df.columns:
                dev_df = df[df['author_email'] == developer.author_email]
                if not dev_df.empty:
                    grp = (
                        dev_df.groupby('batch_id')
                        .agg(total_contribution=('contribution', 'sum'), commits=('hash', 'count'))
                        .reset_index()
                    )
                    # Join with batch metrics for importance and context
                    batch_qs = analysis.batch_metrics.all().values('batch_id', 'importance', 'commit_count', 'unique_authors')
                    batch_df = pd.DataFrame(list(batch_qs))
                    if not batch_df.empty:
                        grp = grp.merge(batch_df, on='batch_id', how='left')
                    grp = grp.sort_values('total_contribution', ascending=False).head(20)
                    top_build_rows = grp.to_dict('records')
    except Exception:
        top_build_rows = []

    # Fallback to the most important builds overall if per-dev not available
    if not top_build_rows:
        top_build_rows = list(
            analysis.batch_metrics.all().order_by('-total_contribution').values(
                'batch_id', 'importance', 'commit_count', 'unique_authors'
            )[:20]
        )

    context = {
        'analysis': analysis,
        'developer': developer,
        'top_build_rows': top_build_rows,
    }
    return render(request, 'dev_productivity/developer_detail.html', context)


def batch_detail(request, analysis_id, batch_id):
    """Show detailed metrics for a specific batch"""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    batch = get_object_or_404(
        BatchMetrics, 
        analysis=analysis, 
        batch_id=batch_id
    )

    # Find top developers (fallback: top by total commits overall)
    batch_developers = analysis.developer_scores.all().order_by('-fds_score')[:20]

    context = {
        'analysis': analysis,
        'batch': batch,
        'batch_developers': batch_developers,
    }
    return render(request, 'dev_productivity/batch_detail.html', context)


def compare_developers(request, analysis_id):
    """Disabled compare view to simplify UX until stable."""
    return redirect('analysis_detail', analysis_id=analysis_id)


# ===================== Helpers =====================

def _try_backfill_developer_scores(analysis: FDSAnalysis) -> None:
    """Attempt to backfill DeveloperScore rows from CSV artifacts on disk."""
    try:
        folder = _get_artifacts_folder(analysis)

        fds_scores_csv = folder / 'fds_scores.csv'
        detailed_csv = folder / 'detailed_metrics.csv'
        if not fds_scores_csv.exists() or not detailed_csv.exists():
            return

        fds_scores = pd.read_csv(fds_scores_csv)
        detailed = pd.read_csv(detailed_csv)

        # Index detailed by author_email for quick lookup
        if 'author_email' not in detailed.columns:
            return
        detailed_idx = detailed.set_index('author_email')

        created = 0
        for _, row in fds_scores.iterrows():
            email = row.get('author_email')
            if not email:
                continue
            if analysis.developer_scores.filter(author_email=email).exists():
                continue

            d = detailed_idx.loc[email] if email in detailed_idx.index else None

            DeveloperScore.objects.create(
                analysis=analysis,
                author_email=email,
                fds_score=float(row.get('fds', 0) or 0),
                avg_effort=float(row.get('avg_effort', 0) or 0),
                avg_importance=float(row.get('avg_importance', 0) or 0),
                total_commits=int(row.get('commit_count', 0) or 0),
                unique_batches=int(row.get('unique_batches', 0) or 0),
                total_churn=float(row.get('total_churn', 0) or 0),
                total_files=int(row.get('total_files', 0) or 0),
                share_mean=float((d.get('share_mean') if d is not None else 0) or 0),
                scale_z_mean=float((d.get('scale_z_mean') if d is not None else 0) or 0),
                reach_z_mean=float((d.get('reach_z_mean') if d is not None else 0) or 0),
                centrality_z_mean=float((d.get('centrality_z_mean') if d is not None else 0) or 0),
                dominance_z_mean=float((d.get('dominance_z_mean') if d is not None else 0) or 0),
                novelty_z_mean=float((d.get('novelty_z_mean') if d is not None else 0) or 0),
                speed_z_mean=float((d.get('speed_z_mean') if d is not None else 0) or 0),
                first_commit_date=pd.to_datetime(row.get('first_commit'), utc=True, errors='coerce') or timezone.now(),
                last_commit_date=pd.to_datetime(row.get('last_commit'), utc=True, errors='coerce') or timezone.now(),
                activity_span_days=float((d.get('activity_span_days') if d is not None else 0) or 0),
            )
            created += 1
        if created:
            analysis.refresh_from_db()
    except Exception:
        # Non-fatal; page can still render without developer scores
        return


def download_analysis_csvs(request, analysis_id: int):
    """Bundle and download all CSV artifacts for a given analysis as a ZIP archive."""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    # Locate artifact folder
    repo_sanitized, folder = _get_repo_key_and_folder(analysis)

    if not folder.exists():
        return JsonResponse({'error': 'No artifacts directory found for this analysis.'}, status=404)

    # Collect CSV files
    csv_files = list(folder.glob('*.csv'))
    if not csv_files:
        return JsonResponse({'error': 'No CSV files found for this analysis.'}, status=404)

    # Build ZIP in-memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in csv_files:
            try:
                zf.write(p, arcname=p.name)
            except Exception:
                continue

    buffer.seek(0)
    from django.http import HttpResponse
    filename = f"analysis_{analysis.id}_{repo_sanitized}_csvs.zip"
    resp = HttpResponse(buffer.getvalue(), content_type='application/zip')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


def _get_repo_key_and_folder(analysis: FDSAnalysis):
    base_dir = Path(__file__).resolve().parents[1]
    repo_sanitized = (analysis.repo_url or 'repo').rstrip('/').split('/')[-2:]
    repo_sanitized = '_'.join(repo_sanitized)
    folder = base_dir / 'fds_results' / f"analysis_{analysis.id}_{repo_sanitized}"
    return repo_sanitized, folder


def _get_artifacts_folder(analysis: FDSAnalysis) -> Path:
    return _get_repo_key_and_folder(analysis)[1]


# ===================== Tools Pages =====================

def settings_page(request):
    return render(request, 'dev_productivity/settings.html', {})


def test_runner_page(request):
    return render(request, 'dev_productivity/test_runner.html', {})


@login_required
@require_POST
def delete_analysis(request, analysis_id):
    """Delete an analysis and all related data"""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    
    # Check permissions - only owner can delete
    if analysis.user != request.user:
        raise PermissionDenied("You don't have permission to delete this analysis.")
    
    try:
        repo_name = analysis.get_repo_name()
        
        # Clean up analysis folder
        import shutil
        analysis_folder = analysis.get_analysis_folder()
        if analysis_folder.exists():
            shutil.rmtree(analysis_folder)
        
        # Log activity before deletion
        log_user_activity(
            request.user,
            'analysis_delete',
            f'Deleted analysis for {repo_name}',
            request,
            analysis
        )
        
        analysis.delete()  # This will cascade delete related DeveloperScore and BatchMetrics
        
        messages.success(request, f'Analysis for "{repo_name}" has been successfully deleted.')
        return redirect('user_analyses')
    
    except Exception as e:
        messages.error(request, f'Error deleting analysis: {str(e)}')
        return redirect('analysis_detail', analysis_id=analysis_id)


@login_required
def share_analysis(request, analysis_id):
    """Share analysis with other users"""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    
    # Check permissions - only owner can share
    if analysis.user != request.user:
        raise PermissionDenied("You don't have permission to share this analysis.")
    
    if request.method == 'POST':
        form = AnalysisSharingForm(request.POST)
        if form.is_valid():
            email_addresses = form.cleaned_data['email_addresses']
            
            shared_count = 0
            for email in email_addresses:
                try:
                    user_to_share = User.objects.get(email=email)
                    analysis.shared_with.add(user_to_share)
                    shared_count += 1
                except User.DoesNotExist:
                    messages.warning(request, f'User with email {email} not found.')
            
            if shared_count > 0:
                # Log activity
                log_user_activity(
                    request.user,
                    'analysis_share',
                    f'Shared analysis {analysis.id} with {shared_count} users',
                    request,
                    analysis
                )
                
                messages.success(request, f'Analysis shared with {shared_count} users.')
            
            return redirect('analysis_detail', analysis_id=analysis.id)
    else:
        form = AnalysisSharingForm()
    
    context = {
        'analysis': analysis,
        'form': form,
        'shared_users': analysis.shared_with.all(),
    }
    
    return render(request, 'dev_productivity/share_analysis.html', context)


@login_required
@require_POST
def toggle_analysis_privacy(request, analysis_id):
    """Toggle analysis public/private status"""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    
    # Check permissions - only owner can change privacy
    if analysis.user != request.user:
        raise PermissionDenied("You don't have permission to modify this analysis.")
    
    analysis.is_public = not analysis.is_public
    analysis.save(update_fields=['is_public'])
    
    status = "public" if analysis.is_public else "private"
    messages.success(request, f'Analysis is now {status}.')
    
    return redirect('analysis_detail', analysis_id=analysis.id)


# ===================== Frontend Dashboard Integration =====================

def _z_to_100(z_value: float) -> int:
    try:
        return max(0, min(100, int(round(50 * (float(z_value) + 1)))))
    except Exception:
        return 0


@require_GET
def dashboard(request, analysis_id: int):
    """Render the new integrated dashboard UI (Bootstrap-based)."""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)
    return render(request, 'dev_productivity/dashboard.html', { 'analysis': analysis })


@require_GET
def dashboard_data(request, analysis_id: int):
    """Return JSON data required by the frontend dashboard for the analysis."""
    analysis = get_object_or_404(FDSAnalysis, id=analysis_id)

    # Developers
    dev_rows = list(analysis.developer_scores.all().values(
        'author_email', 'fds_score', 'avg_effort', 'avg_importance',
        'total_churn', 'total_files', 'unique_batches', 'total_commits',
        'share_mean', 'scale_z_mean', 'reach_z_mean', 'centrality_z_mean',
        'dominance_z_mean', 'novelty_z_mean', 'speed_z_mean'
    ))

    developers = []
    for idx, d in enumerate(dev_rows, start=1):
        email = d['author_email'] or f'dev{idx}@example.com'
        name_part = (email.split('@')[0] or 'dev').replace('.', ' ').title()
        avatar = (name_part[:1] + (name_part.split(' ')[1][:1] if len(name_part.split(' ')) > 1 else '')).upper() or 'DV'
        fds = float(d['fds_score'] or 0)
        commit_count = int(d.get('total_commits') or 0)
        unique_batches = int(d.get('unique_batches') or 0)
        total_churn = float(d.get('total_churn') or 0)

        role = 'Contributor'
        if fds > 10:
            role = 'Core Maintainer'
        elif fds > 1:
            role = 'Senior Developer'
        elif commit_count > 10:
            role = 'Regular Contributor'

        developers.append({
            'id': idx,
            'name': name_part,
            'avatar': avatar,
            'role': role,
            'overall': round(fds, 1),
            'scale': _z_to_100(d.get('scale_z_mean', 0)),
            'reach': _z_to_100(d.get('reach_z_mean', 0)),
            'centrality': _z_to_100(d.get('centrality_z_mean', 0)),
            'dominance': _z_to_100(d.get('dominance_z_mean', 0)),
            'novelty': _z_to_100(d.get('novelty_z_mean', 0)),
            'speed': _z_to_100(d.get('speed_z_mean', 0)),
            'batches': unique_batches,
            'avgTBS': int(round(total_churn / commit_count)) if commit_count else 0,
            'qualityScore': _z_to_100(d.get('centrality_z_mean', 0)),
            'email': email,
            'totalChurn': total_churn,
            'totalFiles': int(d.get('total_files') or 0),
            'commitCount': commit_count,
        })

    # Build charts (chunk by 50 builds ordered by batch_id)
    batch_qs = analysis.batch_metrics.all().order_by('batch_id').values('batch_id', 'commit_count', 'importance', 'unique_authors', 'total_churn')
    batches = list(batch_qs)
    # Adaptive chunking so small datasets render multiple points
    import math
    num_batches = len(batches)
    desired_points = min(12, max(1, num_batches))
    chunk_size = max(1, math.ceil(num_batches / desired_points))
    months = []
    batch_counts = []
    quality_scores = []
    dev_counts = []
    churn_per_chunk = []
    for i in range(0, len(batches), chunk_size):
        chunk = batches[i:i+chunk_size]
        start = batches[i]['batch_id'] if chunk else i+1
        end = chunk[-1]['batch_id'] if chunk else start
        months.append(f"Build {start}-{end}")
        batch_counts.append(sum(b['commit_count'] or 0 for b in chunk))
        if chunk:
            quality_scores.append(round(sum((b['importance'] or 0) for b in chunk) / len(chunk) * 100))
            dev_counts.append(round(sum((b['unique_authors'] or 0) for b in chunk) / len(chunk), 2))
            churn_per_chunk.append(round(sum((b['total_churn'] or 0) for b in chunk), 2))
        else:
            quality_scores.append(0)
            dev_counts.append(0)
            churn_per_chunk.append(0)

    # Fallback when no batch metrics exist to plot
    if not months:
        months = [f"Segment {i}" for i in range(1, 5)]
        tc = analysis.total_commits or 0
        per = int(tc / 4) if tc else 0
        batch_counts = [per, per, per, tc - 3 * per if tc else 0]
        quality_scores = [70, 75, 80, 85]
        all_devs = list(analysis.developer_scores.all())
        avg_unique = max(1, int(len(all_devs) / 4))
        dev_counts = [avg_unique, avg_unique + 1, avg_unique + 2, avg_unique + 3]
        total_churn = int(sum(d.total_churn for d in all_devs) or 0)
        cper = int(total_churn / 4) if total_churn else 0
        churn_per_chunk = [cper, cper, cper, total_churn - 3 * cper if total_churn else 0]

    # Clustering parameters (mirroring the ones used in services)
    clustering = {
        'alpha': 0.001,
        'beta': 0.1,
        'gap': 30.0,
        'break_on_merge': True,
        'break_on_author': False,
    }

    summary = {
        'totalCommits': analysis.total_commits or 0,
        'totalBatches': analysis.total_batches or 0,
        'avgCommitsPerBatch': round((analysis.total_commits or 0) / (analysis.total_batches or 1), 2),
        'dataset': analysis.repo_url,
    }

    # Build list of analyses for selector (most recent first)
    analyses_list = [
        {
            'id': a.id,
            'repo_url': a.repo_url,
            'status': a.status,
            'label': f"{a.repo_url} Dataset (Real FDS)",
            'dashboard_url': request.build_absolute_uri(
                request.path.replace(str(analysis_id), str(a.id)).rsplit('/data', 1)[0]
            ),
        }
        for a in FDSAnalysis.objects.all().order_by('-created_at')[:50]
    ]

    # Top builds for bar chart
    top_build_rows = list(
        analysis.batch_metrics.all().order_by('-total_contribution').values('batch_id', 'importance', 'commit_count')[:10]
    )
    top_builds = {
        'labels': [f"Build {r['batch_id']}" for r in top_build_rows],
        'importance': [round((r['importance'] or 0) * 100, 2) for r in top_build_rows],
        'commits': [r['commit_count'] or 0 for r in top_build_rows],
    }

    payload = {
        'summary': summary,
        'clustering': clustering,
        'charts': {
            'months': months or ['Batch 1-50'],
            'batchCounts': batch_counts or [0],
            'qualityScores': quality_scores or [0],
            'devCounts': dev_counts or [0],
            'churnPerChunk': churn_per_chunk or [0],
        },
        'developers': developers,
        'topBuilds': top_builds,
        'analyses': analyses_list,
    }

    return JsonResponse(payload)