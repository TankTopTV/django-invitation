from django.core.management.base import BaseCommand, CommandError
from datetime import datetime, timedelta
from optparse import make_option
from django.contrib.auth.models import User
from invitation.models import InvitationKey

class Command(BaseCommand):
    args = '<invitation code> [<number of days>]'
    help = 'Show the number of users who signed up with this invitation code in the given number of days'

    def handle(self, *args, **options):
        try:
            code = args[0]
        except:
            print "You need to supply an invitation code"
            return

        try:
            if len(args) > 1:
                days = int(args[1])
            else:
                days = None
        except:
            print "Something's wrong with the number of days you entered"
            return

        invite_key = InvitationKey.objects.get(key=code)
        key_users = invite_key.registrant

        if days:
            interval = datetime.now() - timedelta(days=days)
            key_users = key_users.filter(date_joined__gte=interval)
            print "In the last {0} days".format(days)
        print "{0} people signed up with the code {1}".format(key_users.count(), code)

