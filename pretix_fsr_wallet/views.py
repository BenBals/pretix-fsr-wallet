import logging

import requests
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django_scopes import scope

from pretix.base.models import Event, Organizer
from pretix.multidomain.urlreverse import eventreverse

logger = logging.getLogger(__name__)


# View a user comes back to after signing in via OIDC
class OIDCLoginReturnView(View):
    def get(self, request, *args, **kwargs):
        print('OIDC Login Return', request)
        state = request.GET.get('state')
        code = request.GET.get('code')
        print('OIDC Code', code)
        
        # We stored some information in the session in checkout_prepare(),
        # let's compare the new information to double-check that this is about
        # the same payment
        if state == request.session['payment_wallet_oidc_state']:
            # Save the new information to the user's session
            request.session['payment_wallet_code'] = code
            try:
                # Redirect back to the confirm page. We chose to save the
                # event ID in the user's session. We could also put this
                # information into a URL parameter.
                organizer = Organizer.objects.get(pk=request.session['payment_wallet_organizer_pk'])
                with scope(organizer=organizer):
                    event = Event.objects.get(pk=request.session['payment_wallet_event_pk'], organizer=organizer)
                    return redirect(eventreverse(event, 'presale:event.checkout', kwargs={
                        'step': 'confirm',
                    }))
            except Event.DoesNotExist:
                pass  # TODO: Display error message
        else:
            print('Error: Invalid oidc state')
            pass  # TODO: Display error message
