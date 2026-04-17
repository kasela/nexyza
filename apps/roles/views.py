from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from apps.teams.models import Team
from .models import WorkspaceRole, Permission, DEFAULT_ROLE_PERMISSIONS


@login_required
def role_manager(request, team_slug):
    team = get_object_or_404(Team, slug=team_slug)
    if not team.can_user_admin(request.user):
        messages.error(request, 'Admin access required.')
        return redirect('teams:detail', slug=team_slug)
    roles     = WorkspaceRole.objects.filter(team=team)
    all_perms = [(p.value, p.label) for p in Permission]
    return render(request, 'roles/manager.html', {
        'team': team, 'roles': roles,
        'all_permissions':   all_perms,
        'default_roles':     DEFAULT_ROLE_PERMISSIONS,
    })


@login_required
@require_POST
def create_role(request, team_slug):
    team = get_object_or_404(Team, slug=team_slug)
    if not team.can_user_admin(request.user):
        messages.error(request, 'Admin access required.')
        return redirect('teams:detail', slug=team_slug)
    name  = request.POST.get('name', '').strip()
    desc  = request.POST.get('description', '').strip()
    perms = request.POST.getlist('permissions')
    if not name:
        messages.error(request, 'Role name required.')
        return redirect('roles:manager', team_slug=team_slug)
    WorkspaceRole.objects.update_or_create(
        team=team, name=name,
        defaults={'description': desc, 'permissions': perms,
                  'created_by': request.user}
    )
    messages.success(request, f'Role "{name}" saved.')
    return redirect('roles:manager', team_slug=team_slug)


@login_required
@require_POST
def delete_role(request, team_slug, role_id):
    team = get_object_or_404(Team, slug=team_slug)
    if not team.can_user_admin(request.user):
        messages.error(request, 'Admin access required.')
        return redirect('teams:detail', slug=team_slug)
    role = get_object_or_404(WorkspaceRole, pk=role_id, team=team)
    role.delete()
    messages.success(request, f'Role "{role.name}" deleted.')
    return redirect('roles:manager', team_slug=team_slug)
