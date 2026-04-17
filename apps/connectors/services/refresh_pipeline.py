from typing import Any, Dict


def build_refresh_pipeline_summary(connectors, jobs, runs) -> Dict[str, Any]:
    connectors = list(connectors)
    jobs = list(jobs)
    runs = list(runs)
    ok_runs = [r for r in runs if getattr(r, 'status', '') == 'ok']
    return {
        'connector_count': len(connectors),
        'active_jobs': sum(1 for j in jobs if getattr(j, 'is_enabled', False)),
        'recent_runs': len(runs),
        'successful_runs': len(ok_runs),
    }


def build_snapshot_summary(snapshots) -> Dict[str, Any]:
    snapshots = list(snapshots)
    return {
        'snapshot_count': len(snapshots),
        'latest_snapshot_at': getattr(snapshots[0], 'created_at', None) if snapshots else None,
    }
