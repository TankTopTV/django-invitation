from django.conf import settings
from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template


if getattr(settings, 'INVITATION_USE_ALLAUTH', False):
    from allauth.account.forms import BaseSignupForm as RegistrationFormTermsOfService
    reg_backend = 'allauth.account.auth_backends.AuthenticationBackend'
else:
    from registration.forms import RegistrationFormTermsOfService
    reg_backend = 'registration.backends.default.DefaultBackend'

from invitation.views import invite, invited, register

urlpatterns = patterns('',
    url(r'^invite/complete/$',
                direct_to_template,
                {'template': 'invitation/invitation_complete.html'},
                name='invitation_complete'),
    url(r'^invite/$',
                invite,
                name='invitation_invite'),
    url(r'^invited/(?P<invitation_key>\w+)/$',
                invited,
                name='invitation_invited'),
    url(r'^invited/.*',
                invited),
    url(r'^register/$',
                register,
                { 'backend': reg_backend },
                name='registration_register'),
)
