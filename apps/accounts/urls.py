from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('settings/',                    views.settings_hub,            name='settings'),
    path('settings/profile/',            views.update_profile,          name='update_profile'),
    path('settings/password/',           views.change_password,         name='change_password'),
    path('settings/notifications/',      views.update_notifications,    name='update_notifications'),
    path('settings/delete/',             views.delete_account,          name='delete_account'),
    path('verify-email/send/',           views.send_verification_email, name='send_verification'),
    path('verify-email/<str:token>/',    views.verify_email,            name='verify_email'),
    path('profile/',                     views.profile_redirect,        name='profile'),
    path('onboarding/dismiss/',          views.dismiss_onboarding,      name='dismiss_onboarding'),
]
