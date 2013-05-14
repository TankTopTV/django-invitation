from django.conf import settings
from django.views.generic.simple import direct_to_template
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site

if getattr(settings, 'INVITATION_USE_ALLAUTH', False):
    from allauth.socialaccount.views import signup as allauth_signup
    from allauth.socialaccount.forms import SignupForm as RegistrationForm
    registration_template = 'accounts/signup.html'

    def registration_register(request, backend, success_url, form_class, disallowed_url, template_name, extra_context):
        return allauth_signup(request, template_name=template_name)
else:
    from registration.views import register as registration_register
    from registration.forms import RegistrationForm
    registration_template = 'registration/registration_form.html'

from invitation.models import InvitationKey
from invitation.forms import InvitationKeyForm
from invitation.backends import InvitationBackend

is_key_valid = InvitationKey.objects.is_key_valid
get_key = InvitationKey.objects.get_key

remaining_invitations_for_user = InvitationKey.objects.remaining_invitations_for_user

def invited(request, invitation_key=None, extra_context=None):
    if getattr(settings, 'INVITE_MODE', False):
        extra_context = extra_context is not None and extra_context.copy() or {}
        if invitation_key and is_key_valid(invitation_key):
            template_name = 'invitation/invited.html'
        else:
            if invitation_key:
                extra_context.update({'invitation_key': invitation_key})
                ik = get_key(invitation_key)
                if ik:
                    if ik.key_expired():
                        extra_context.update({'expired_key': True})
                    else:
                        assert ik.uses_left == 0
                        extra_context.update({'no_uses_left_key': True})
                else:
                    extra_context.update({'invalid_key': True})
            else:
                extra_context.update({'no_key': True})
            template_name = 'invitation/wrong_invitation_key.html'
        extra_context.update({'invitation_key': invitation_key})
        request.session['invitation_key'] = invitation_key
        return direct_to_template(request, template_name, extra_context)
    else:
        return HttpResponseRedirect(reverse('registration_register'))

def register(request, backend, success_url=None,
            form_class=RegistrationForm,
            disallowed_url='registration_disallowed',
            post_registration_redirect=None,
            template_name=registration_template,
            wrong_template_name='invitation/wrong_invitation_key.html',
            extra_context=None):
    extra_context = extra_context is not None and extra_context.copy() or {}
    if getattr(settings, 'INVITE_MODE', False):
        invitation_key = request.REQUEST.get('invitation_key', False)
        if invitation_key:
            extra_context.update({'invitation_key': invitation_key})
            if is_key_valid(invitation_key):
                return registration_register(request, backend, success_url,
                                            form_class, disallowed_url,
                                            template_name, extra_context)
            else:
                extra_context.update({'invalid_key': True})
        else:
            extra_context.update({'no_key': True})
        return direct_to_template(request, wrong_template_name, extra_context)
    else:
        return registration_register(request, backend, success_url, form_class,
                                     disallowed_url, template_name, extra_context)

def invite(request, success_url=None,
            form_class=InvitationKeyForm,
            template_name='invitation/invitation_form.html',
            extra_context=None):
    extra_context = extra_context is not None and extra_context.copy() or {}
    remaining_invitations = remaining_invitations_for_user(request.user)
    if request.method == 'POST':
        form = form_class(data=request.POST, files=request.FILES, 
                          remaining_invitations=remaining_invitations, 
                          user_email=request.user.email)
        if form.is_valid():
            invitation = InvitationKey.objects.create_invitation(request.user)
            invitation.send_to(form.cleaned_data["email"])
            # success_url needs to be dynamically generated here; setting a
            # a default value using reverse() will cause circular-import
            # problems with the default URLConf for this application, which
            # imports this file.
            return HttpResponseRedirect(success_url or reverse('invitation_complete'))
    else:
        form = form_class()

    email_preview = render_to_string('invitation/invitation_email.txt',
                                   { 'invitation_key': None,
                                     'expiration_days': settings.ACCOUNT_INVITATION_DAYS,
                                     'from_user': request.user,
                                     'site': Site.objects.get_current() })
    extra_context.update({
            'form': form,
            'remaining_invitations': remaining_invitations,
            'email_preview': email_preview,
        })
    return direct_to_template(request, template_name, extra_context)
invite = login_required(invite)
