from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from dev_productivity.models import FDSAnalysis, DeveloperScore, BatchMetrics
from datetime import timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Create example analyses that are visible to all registered users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing example analyses first',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Deleting existing example analyses...')
            FDSAnalysis.objects.filter(repo_url__in=[
                'https://github.com/vercel/next.js',
                'https://github.com/apache/kafka',
                'https://github.com/torvalds/linux'
            ]).delete()

        # Create or get the example user
        example_user, created = User.objects.get_or_create(
            email='examples@fds-analyzer.com',
            defaults={
                'username': 'fds_examples',
                'first_name': 'FDS',
                'last_name': 'Examples',
                'is_active': True,
                'email_verified': True,
                'github_access_token': 'example_token',
            }
        )

        if created:
            example_user.set_unusable_password()
            example_user.save()
            self.stdout.write(f'Created example user: {example_user.email}')

        # Define the example analyses
        example_analyses = [
            {
                'repo_url': 'https://github.com/vercel/next.js',
                'commit_limit': 300,
                'total_commits': 221,
                'total_developers': 94,
                'total_batches': 89,
                'execution_time': 634.9,
                'developers_data': [
                    {'email': 'timneutkens@gmail.com', 'fds_score': 15.8, 'commits': 45, 'batches': 23},
                    {'email': 'jj@jjsweb.site', 'fds_score': 12.3, 'commits': 32, 'batches': 18},
                    {'email': 'shu@vercel.com', 'fds_score': 10.7, 'commits': 28, 'batches': 15},
                    {'email': 'ijjk@users.noreply.github.com', 'fds_score': 9.2, 'commits': 25, 'batches': 14},
                    {'email': 'styfle@gmail.com', 'fds_score': 8.4, 'commits': 22, 'batches': 12},
                ]
            },
            {
                'repo_url': 'https://github.com/apache/kafka',
                'commit_limit': 300,
                'total_commits': 225,
                'total_developers': 157,
                'total_batches': 112,
                'execution_time': 597.6,
                'developers_data': [
                    {'email': 'cmccabe@apache.org', 'fds_score': 18.2, 'commits': 38, 'batches': 24},
                    {'email': 'jgus@confluent.io', 'fds_score': 14.6, 'commits': 29, 'batches': 19},
                    {'email': 'dajac@confluent.io', 'fds_score': 13.1, 'commits': 26, 'batches': 17},
                    {'email': 'hachikuji@gmail.com', 'fds_score': 11.8, 'commits': 23, 'batches': 15},
                    {'email': 'kowshik@confluent.io', 'fds_score': 10.3, 'commits': 20, 'batches': 13},
                ]
            },
            {
                'repo_url': 'https://github.com/torvalds/linux',
                'commit_limit': 300,
                'total_commits': 119,
                'total_developers': 117,
                'total_batches': 95,
                'execution_time': 129.8,
                'developers_data': [
                    {'email': 'torvalds@linux-foundation.org', 'fds_score': 22.4, 'commits': 15, 'batches': 12},
                    {'email': 'akpm@linux-foundation.org', 'fds_score': 16.7, 'commits': 12, 'batches': 10},
                    {'email': 'davem@davemloft.net', 'fds_score': 14.2, 'commits': 10, 'batches': 8},
                    {'email': 'gregkh@linuxfoundation.org', 'fds_score': 12.9, 'commits': 9, 'batches': 7},
                    {'email': 'mingo@kernel.org', 'fds_score': 11.3, 'commits': 8, 'batches': 6},
                ]
            }
        ]

        for analysis_data in example_analyses:
            # Create the analysis
            analysis, created = FDSAnalysis.objects.get_or_create(
                user=example_user,
                repo_url=analysis_data['repo_url'],
                defaults={
                    'access_token': 'example_token',
                    'commit_limit': analysis_data['commit_limit'],
                    'status': 'completed',
                    'created_at': timezone.now() - timedelta(days=random.randint(1, 30)),
                    'started_at': timezone.now() - timedelta(days=random.randint(1, 30)),
                    'completed_at': timezone.now() - timedelta(days=random.randint(0, 29)),
                    'total_commits': analysis_data['total_commits'],
                    'total_developers': analysis_data['total_developers'],
                    'total_batches': analysis_data['total_batches'],
                    'execution_time': analysis_data['execution_time'],
                    'is_public': True,  # Make visible to all users
                }
            )

            if created:
                self.stdout.write(f'Created analysis: {analysis.repo_url}')

                # Create developer scores
                for dev_data in analysis_data['developers_data']:
                    DeveloperScore.objects.create(
                        analysis=analysis,
                        author_email=dev_data['email'],
                        fds_score=dev_data['fds_score'],
                        avg_effort=random.uniform(0.3, 0.8),
                        avg_importance=random.uniform(0.4, 0.9),
                        total_commits=dev_data['commits'],
                        unique_batches=dev_data['batches'],
                        total_churn=random.randint(1000, 10000),
                        total_files=random.randint(50, 500),
                        share_mean=random.uniform(0.1, 0.9),
                        scale_z_mean=random.uniform(-2, 2),
                        reach_z_mean=random.uniform(-2, 2),
                        centrality_z_mean=random.uniform(-2, 2),
                        dominance_z_mean=random.uniform(-2, 2),
                        novelty_z_mean=random.uniform(-2, 2),
                        speed_z_mean=random.uniform(-2, 2),
                        first_commit_date=timezone.now() - timedelta(days=random.randint(30, 365)),
                        last_commit_date=timezone.now() - timedelta(days=random.randint(0, 30)),
                        activity_span_days=random.uniform(1, 365),
                    )

                # Create some batch metrics
                for i in range(min(10, analysis_data['total_batches'])):
                    BatchMetrics.objects.create(
                        analysis=analysis,
                        batch_id=i + 1,
                        unique_authors=random.randint(1, 5),
                        total_contribution=random.uniform(5, 50),
                        avg_contribution=random.uniform(1, 10),
                        max_contribution=random.uniform(10, 30),
                        avg_effort=random.uniform(0.2, 0.8),
                        importance=random.uniform(0.3, 0.9),
                        total_churn=random.randint(100, 5000),
                        total_files=random.randint(5, 100),
                        commit_count=random.randint(1, 20),
                        start_date=timezone.now() - timedelta(days=random.randint(1, 365)),
                        end_date=timezone.now() - timedelta(days=random.randint(0, 364)),
                        duration_hours=random.uniform(0.5, 168),  # Up to 1 week
                    )

            else:
                self.stdout.write(f'Analysis already exists: {analysis.repo_url}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created/verified {len(example_analyses)} example analyses'
            )
        )
        
        # Display summary
        self.stdout.write('\nExample analyses created:')
        for analysis in FDSAnalysis.objects.filter(user=example_user):
            self.stdout.write(
                f'  - {analysis.repo_url} ({analysis.total_developers} developers, '
                f'{analysis.total_commits} commits, {analysis.total_batches} batches)'
            )
