from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta
from .models import Team, TeamMembership, TeamInvite, SharedUpload


@login_required
def team_list(request):
    owned   = Team.objects.filter(owner=request.user).prefetch_related('memberships')
    member  = TeamMembership.objects.filter(user=request.user).exclude(
        team__owner=request.user).select_related('team')
    return render(request, 'teams/list.html', {
        'owned_teams': owned, 'member_teams': member
    })


@login_required
@require_POST
def create_team(request):
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Team name required')
        return redirect('teams:list')
    base_slug = slugify(name)
    slug = base_slug
    i = 1
    while Team.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{i}"; i += 1
    team = Team.objects.create(name=name, slug=slug, owner=request.user)
    TeamMembership.objects.create(team=team, user=request.user, role='admin',
                                  invited_by=request.user)
    messages.success(request, f'Team "{name}" created.')
    return redirect('teams:detail', slug=slug)


@login_required
def team_detail(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not team.can_user_read(request.user):
        messages.error(request, 'Access denied')
        return redirect('teams:list')
    members  = team.memberships.select_related('user').order_by('role', 'joined_at')
    shared   = team.shared_uploads.select_related('upload', 'shared_by').order_by('-shared_at')
    is_admin = team.can_user_admin(request.user)
    is_owner = team.owner == request.user
    return render(request, 'teams/detail.html', {
        'team': team, 'members': members,
        'shared_uploads': shared,
        'is_admin': is_admin, 'is_owner': is_owner,
    })


@login_required
@require_POST
def invite_member(request, slug):
    team  = get_object_or_404(Team, slug=slug)
    if not team.can_user_admin(request.user):
        messages.error(request, 'Admin access required'); return redirect('teams:detail', slug=slug)
    email = request.POST.get('email', '').strip().lower()
    role  = request.POST.get('role', 'viewer')
    if not email:
        messages.error(request, 'Email required'); return redirect('teams:detail', slug=slug)
    # Check if already member
    from django.contrib.auth import get_user_model
    User = get_user_model()
    existing_user = User.objects.filter(email=email).first()
    if existing_user and TeamMembership.objects.filter(team=team, user=existing_user).exists():
        messages.warning(request, f'{email} is already a member')
        return redirect('teams:detail', slug=slug)
    # Create invite
    expires = timezone.now() + timedelta(days=7)
    invite, created = TeamInvite.objects.update_or_create(
        team=team, email=email,
        defaults={'role': role, 'invited_by': request.user,
                  'expires_at': expires, 'accepted': False}
    )
    # If user exists, add immediately
    if existing_user:
        TeamMembership.objects.get_or_create(
            team=team, user=existing_user,
            defaults={'role': role, 'invited_by': request.user}
        )
        messages.success(request, f'{email} added to team as {role}')
    else:
        messages.success(request, f'Invite sent to {email}')
    return redirect('teams:detail', slug=slug)


@login_required
@require_POST
def remove_member(request, slug, user_id):
    team = get_object_or_404(Team, slug=slug)
    if not team.can_user_admin(request.user):
        messages.error(request, 'Admin access required'); return redirect('teams:detail', slug=slug)
    from django.contrib.auth import get_user_model
    target = get_object_or_404(get_user_model(), pk=user_id)
    if target == team.owner:
        messages.error(request, 'Cannot remove team owner'); return redirect('teams:detail', slug=slug)
    TeamMembership.objects.filter(team=team, user=target).delete()
    messages.success(request, f'{target.email} removed')
    return redirect('teams:detail', slug=slug)


@login_required
def accept_invite(request, token):
    invite = get_object_or_404(TeamInvite, token=token)
    if invite.accepted:
        messages.info(request, 'Invite already used'); return redirect('teams:list')
    if timezone.now() > invite.expires_at:
        messages.error(request, 'Invite has expired'); return redirect('teams:list')
    TeamMembership.objects.get_or_create(
        team=invite.team, user=request.user,
        defaults={'role': invite.role, 'invited_by': invite.invited_by}
    )
    invite.accepted = True; invite.save(update_fields=['accepted'])
    messages.success(request, f'Joined {invite.team.name}!')
    return redirect('teams:detail', slug=invite.team.slug)
