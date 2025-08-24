from django.core.management.base import BaseCommand
from dev_productivity.models import FDSParameterSet


class Command(BaseCommand):
    help = 'Create default FDS parameter presets'

    def handle(self, *args, **options):
        presets = [
            {
                'name': 'Default (Balanced)',
                'preset_type': 'default',
                'is_system_preset': True,
                'torque_alpha': 0.001,
                'torque_beta': 0.1,
                'torque_gap': 30.0,
                # Effort weights (sum = 1.0)
                'effort_share_weight': 0.25,
                'effort_scale_weight': 0.15,
                'effort_reach_weight': 0.20,
                'effort_centrality_weight': 0.20,
                'effort_dominance_weight': 0.15,
                'effort_novelty_weight': 0.05,
                'effort_speed_weight': 0.05,
                # Importance weights (sum = 1.0)
                'importance_scale_weight': 0.30,
                'importance_scope_weight': 0.20,
                'importance_centrality_weight': 0.15,
                'importance_complexity_weight': 0.15,
                'importance_type_weight': 0.10,
                'importance_release_weight': 0.10,
                # General thresholds
                'noise_threshold': 0.1,
                'contribution_threshold': 0.01,
                'pagerank_damping': 0.85,
                'min_churn_for_edge': 2,
            },
            {
                'name': 'Time Sensitive',
                'preset_type': 'time_sensitive',
                'is_system_preset': True,
                'torque_alpha': 0.005,
                'torque_beta': 0.05,
                'torque_gap': 15.0,
                # Effort weights (sum = 1.0)
                'effort_share_weight': 0.20,
                'effort_scale_weight': 0.10,
                'effort_reach_weight': 0.15,
                'effort_centrality_weight': 0.15,
                'effort_dominance_weight': 0.20,
                'effort_novelty_weight': 0.10,
                'effort_speed_weight': 0.10,
                # Importance weights (sum = 1.0)
                'importance_scale_weight': 0.25,
                'importance_scope_weight': 0.25,
                'importance_centrality_weight': 0.20,
                'importance_complexity_weight': 0.10,
                'importance_type_weight': 0.10,
                'importance_release_weight': 0.10,
                # General thresholds
                'noise_threshold': 0.05,
                'contribution_threshold': 0.005,
                'pagerank_damping': 0.90,
                'min_churn_for_edge': 1,
            },
            {
                'name': 'Complexity Focused',
                'preset_type': 'complexity_focused',
                'is_system_preset': True,
                'torque_alpha': 0.0005,
                'torque_beta': 0.2,
                'torque_gap': 50.0,
                # Effort weights (sum = 1.0)
                'effort_share_weight': 0.15,
                'effort_scale_weight': 0.25,
                'effort_reach_weight': 0.15,
                'effort_centrality_weight': 0.25,
                'effort_dominance_weight': 0.10,
                'effort_novelty_weight': 0.10,
                'effort_speed_weight': 0.00,
                # Importance weights (sum = 1.0)
                'importance_scale_weight': 0.20,
                'importance_scope_weight': 0.15,
                'importance_centrality_weight': 0.15,
                'importance_complexity_weight': 0.35,
                'importance_type_weight': 0.15,
                'importance_release_weight': 0.00,
                # General thresholds
                'noise_threshold': 0.15,
                'contribution_threshold': 0.02,
                'pagerank_damping': 0.80,
                'min_churn_for_edge': 3,
            },
            {
                'name': 'Contribution Focused',
                'preset_type': 'contribution_focused',
                'is_system_preset': True,
                'torque_alpha': 0.002,
                'torque_beta': 0.08,
                'torque_gap': 25.0,
                # Effort weights (sum = 1.0)
                'effort_share_weight': 0.40,
                'effort_scale_weight': 0.15,
                'effort_reach_weight': 0.25,
                'effort_centrality_weight': 0.10,
                'effort_dominance_weight': 0.10,
                'effort_novelty_weight': 0.00,
                'effort_speed_weight': 0.00,
                # Importance weights (sum = 1.0)
                'importance_scale_weight': 0.40,
                'importance_scope_weight': 0.30,
                'importance_centrality_weight': 0.10,
                'importance_complexity_weight': 0.05,
                'importance_type_weight': 0.05,
                'importance_release_weight': 0.10,
                # General thresholds
                'noise_threshold': 0.08,
                'contribution_threshold': 0.001,
                'pagerank_damping': 0.85,
                'min_churn_for_edge': 2,
            }
        ]

        created_count = 0
        updated_count = 0

        for preset_data in presets:
            preset, created = FDSParameterSet.objects.update_or_create(
                name=preset_data['name'],
                is_system_preset=True,
                defaults=preset_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created preset: {preset.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated preset: {preset.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nParameter presets setup complete!'
                f'\nCreated: {created_count} presets'
                f'\nUpdated: {updated_count} presets'
            )
        )

