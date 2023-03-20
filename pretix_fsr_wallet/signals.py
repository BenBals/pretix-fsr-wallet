import json
import re

import requests
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from pretix.base.services.orders import Order
from pretix.base.settings import settings_hierarkey
from pretix.control.signals import nav_event_settings
from pretix.presale.signals import (
    contact_form_fields_overrides,
)
from pretix.presale.views import get_cart


@receiver(nav_event_settings, dispatch_uid="fsr_wallet_nav")
def navbar_info(sender, request, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(
            request.organizer, request.event, "can_change_event_settings", request=request
    ):
        return []
    return [
        {
            "label": _("FSR Wallet"),
            "url": reverse(
                "plugins:pretix_fsr_wallet:settings",
                kwargs={
                    "event": request.event.slug,
                    "organizer": request.organizer.slug,
                },
            ),
            "active": url.namespace == "plugins:pretix_fsr_wallet",
        }
    ]

default_config = {
    'wallet_backend:url': 'https://api.wallet.myhpi.de',
    'oidc:url': 'https://oidc.hpi.de',
}

settings_hierarkey.add_default("fsr_wallet_config", json.dumps(default_config, cls=I18nJSONEncoder), dict)
