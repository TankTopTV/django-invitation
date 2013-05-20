import os
import random
import datetime
from django.db import models
from django.conf import settings
from django.utils.http import int_to_base36
from django.utils.hashcompat import sha_constructor
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.utils.timezone import now

if getattr(settings, 'INVITATION_USE_ALLAUTH', False):
    import re
    SHA1_RE = re.compile('^[a-f0-9]{40}$')
else:
    from registration.models import SHA1_RE

class InvitationKeyManager(models.Manager):
    def get_key(self, invitation_key):
        """
        Return InvitationKey, or None if it doesn't (or shouldn't) exist.
        """
        try:
            key = self.get(key=invitation_key)
        except self.model.DoesNotExist:
            return None

        return key

    def is_key_valid(self, invitation_key):
        """
        Check if an ``InvitationKey`` is valid or not, returning a boolean,
        ``True`` if the key is valid.
        """
        invitation_key = self.get_key(invitation_key)
        return invitation_key and invitation_key.is_usable()

    def create_invitation(self, user):
        """
        Create an ``InvitationKey`` and returns it.

        The key for the ``InvitationKey`` will be a SHA1 hash, generated
        from a combination of the ``User``'s username and a random salt.
        """
        salt = sha_constructor(str(random.random())).hexdigest()[:5]
        key = sha_constructor("%s%s%s" % (datetime.datetime.now(), salt, user.username)).hexdigest()
        return self.create(from_user=user, key=key)

    def create_bulk_invitation(self, user, key, uses):
        """ Create a set of invitation keys - these can be used by anyone, not just a specific recipient """
        return self.create(from_user=user, key=key, uses_left=uses)

    def remaining_invitations_for_user(self, user):
        """
        Return the number of remaining invitations for a given ``User``.
        """
        invitation_user, created = InvitationUser.objects.get_or_create(
            inviter=user,
            defaults={'invitations_remaining': settings.INVITATIONS_PER_USER})
        return invitation_user.invitations_remaining

    def delete_expired_keys(self):
        for key in self.all():
            if key.key_expired():
                key.delete()


class InvitationKey(models.Model):
    key = models.CharField(_('invitation key'), max_length=40, db_index=True)
    date_invited = models.DateTimeField(_('date invited'),
                                        auto_now_add=True)
    from_user = models.ForeignKey(User,
                                  related_name='invitations_sent')
    registrant = models.ManyToManyField(User, null=True, blank=True,
                                        related_name='invitations_used')
    uses_left = models.IntegerField(default=1)
    # -1 duration means the key won't expire
    duration = models.IntegerField(default=settings.ACCOUNT_INVITATION_DAYS, null=True)

    objects = InvitationKeyManager()

    def __unicode__(self):
        return u"Invitation from %s on %s (%s)" % (self.from_user.username, self.date_invited, self.key)

    def is_usable(self):
        """
        Return whether this key is still valid for registering a new user.
        """
        return self.uses_left > 0 and not self.key_expired()

    def _expiry_date(self):
        # Assumes the duration is positive
        assert self.duration != -1
        expiration_duration = self.duration or settings.ACCOUNT_INVITATION_DAYS
        expiration_date = datetime.timedelta(days=expiration_duration)
        return self.date_invited + expiration_date

    def key_expired(self):
        """
        Determine whether this ``InvitationKey`` has expired, returning
        a boolean -- ``True`` if the key has expired.

        The date the key has been created is incremented by the number of days
        specified in the setting ``ACCOUNT_INVITATION_DAYS`` (which should be
        the number of days after invite during which a user is allowed to
        create their account); if the result is less than or equal to the
        current date, the key has expired and this method returns ``True``.

        """
        if self.duration == -1:
            return False

        return self._expiry_date() <= now()
    key_expired.boolean = True

    def expiry_date(self):
        if self.duration == -1:
            return 'never'
        return self._expiry_date().strftime('%d %b %Y %H:%M')

    expiry_date.short_description = 'Expiry date'

    def mark_used(self, registrant):
        """
        Note that this key has been used to register a new user.
        """
        self.uses_left -= 1
        self.registrant.add(registrant)
        self.save()

    def send_to(self, email):
        """
        Send an invitation email to ``email``.
        """
        current_site = Site.objects.get_current()

        subject = render_to_string('invitation/invitation_email_subject.txt',
                                   { 'site': current_site,
                                     'invitation_key': self })
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())

        message = render_to_string('invitation/invitation_email.txt',
                                   { 'invitation_key': self,
                                     'expiration_days': settings.ACCOUNT_INVITATION_DAYS,
                                     'from_user': self.from_user,
                                     'site': current_site })

        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])


class InvitationUser(models.Model):
    inviter = models.ForeignKey(User, unique=True)
    invitations_remaining = models.IntegerField()

    def __unicode__(self):
        return u"InvitationUser for %s" % self.inviter.username


def user_post_save(sender, instance, created, **kwargs):
    """Create InvitationUser for user when User is created."""
    if created:
        invitation_user = InvitationUser()
        invitation_user.inviter = instance
        invitation_user.invitations_remaining = settings.INVITATIONS_PER_USER
        invitation_user.save()

models.signals.post_save.connect(user_post_save, sender=User)

def invitation_key_post_save(sender, instance, created, **kwargs):
    """Decrement invitations_remaining when InvitationKey is created."""
    if created:
        invitation_user = InvitationUser.objects.get(inviter=instance.from_user)
        remaining = invitation_user.invitations_remaining
        invitation_user.invitations_remaining = remaining-1
        invitation_user.save()

models.signals.post_save.connect(invitation_key_post_save, sender=InvitationKey)
