from django.contrib.auth import update_session_auth_hash, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import User


@login_required
def settings_hub(request):
    """Central account settings page — profile, password, notifications, danger zone."""
    sub = getattr(request, 'subscription', None)
    from apps.analyser.models import FileUpload
    from apps.audit.models import AuditEvent
    upload_count = FileUpload.objects.filter(user=request.user).count()
    recent_events = AuditEvent.objects.filter(user=request.user)[:5]
    COMMON_TIMEZONES = [
        'UTC','Asia/Colombo','Asia/Kolkata','Asia/Singapore','Asia/Tokyo',
        'America/New_York','America/Chicago','America/Los_Angeles','America/Sao_Paulo',
        'Europe/London','Europe/Paris','Europe/Berlin','Australia/Sydney',
    ]
    notif_prefs = [
        ('notify_pipeline', 'Email me when a pipeline runs', request.user.notify_on_pipeline),
        ('notify_alert',    'Email me when a data alert triggers', request.user.notify_on_alert),
        ('notify_digest',   'Send weekly digest reports', request.user.notify_digest),
    ]
    return render(request, 'accounts/settings.html', {
        'sub': sub,
        'upload_count': upload_count,
        'recent_events': recent_events,
        'password_form': PasswordChangeForm(request.user),
        'timezones': COMMON_TIMEZONES,
        'notif_prefs': notif_prefs,
    })


@login_required
@require_POST
def update_profile(request):
    user = request.user
    user.first_name = request.POST.get('first_name', '').strip()[:30]
    user.last_name  = request.POST.get('last_name',  '').strip()[:30]
    user.bio        = request.POST.get('bio', '').strip()[:200]
    user.timezone   = request.POST.get('timezone', 'UTC')[:60]

    if 'avatar' in request.FILES:
        # Delete old avatar
        if user.avatar:
            import os
            try: os.remove(user.avatar.path)
            except: pass
        user.avatar = request.FILES['avatar']

    user.save()
    messages.success(request, 'Profile updated.')
    return redirect('accounts:settings')


@login_required
@require_POST
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        messages.success(request, 'Password changed successfully.')
    else:
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, f'{field}: {e}')
    return redirect('accounts:settings')


@login_required
@require_POST
def update_notifications(request):
    user = request.user
    user.notify_on_pipeline = 'notify_pipeline' in request.POST
    user.notify_on_alert    = 'notify_alert' in request.POST
    user.notify_digest      = 'notify_digest' in request.POST
    user.save(update_fields=['notify_on_pipeline', 'notify_on_alert', 'notify_digest'])
    messages.success(request, 'Notification preferences saved.')
    return redirect('accounts:settings')


@login_required
@require_POST
def delete_account(request):
    """Hard delete — asks for password confirmation."""
    password = request.POST.get('confirm_password', '')
    if not request.user.check_password(password):
        messages.error(request, 'Incorrect password. Account not deleted.')
        return redirect('accounts:settings')

    user = request.user
    # Delete all files
    from apps.analyser.models import FileUpload
    for upload in FileUpload.objects.filter(user=user):
        try: upload.file.delete(save=False)
        except: pass
    logout(request)
    user.delete()
    messages.success(request, 'Your account has been permanently deleted.')
    return redirect('core:home')


@login_required
def send_verification_email(request):
    user = request.user
    if user.is_email_verified:
        messages.info(request, 'Email already verified.')
        return redirect('accounts:settings')
    token = user.generate_email_token()
    user.save(update_fields=['email_verify_token'])
    # Send email
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        verify_url = request.build_absolute_uri(f'/accounts/verify-email/{token}/')
        send_mail(
            subject='Verify your Nexyza email',
            message=f'Click to verify: {verify_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass
    messages.success(request, f'Verification email sent to {user.email}.')
    return redirect('accounts:settings')


def verify_email(request, token):
    try:
        user = User.objects.get(email_verify_token=token, is_email_verified=False)
        user.is_email_verified = True
        user.email_verify_token = ''
        user.save(update_fields=['is_email_verified', 'email_verify_token'])
        messages.success(request, 'Email verified! ✓')
    except User.DoesNotExist:
        messages.error(request, 'Invalid or expired verification link.')
    return redirect('accounts:settings')


@login_required
def profile_redirect(request):
    return redirect('accounts:settings')


@login_required
@require_POST
def dismiss_onboarding(request):
    from .models import OnboardingState
    state, _ = OnboardingState.objects.get_or_create(user=request.user)
    state.dismissed = True
    state.save(update_fields=['dismissed'])
    from django.http import JsonResponse
    return JsonResponse({'ok': True})


def _get_or_create_onboarding(user):
    from .models import OnboardingState
    state, _ = OnboardingState.objects.get_or_create(user=user)
    return state
