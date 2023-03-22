import json

from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from pretix.base.settings import settings_hierarkey
from pretix.base.signals import register_payment_providers

from .payment import Wallet

@receiver(register_payment_providers, dispatch_uid="payment_wallet")
def register_payment_provider(sender, **kwargs):
    return [Wallet]

default_config = {
    'wallet_backend:url': 'https://api.wallet.myhpi.de',
    'oidc:url': 'https://oidc.hpi.de',
}

settings_hierarkey.add_default("fsr_wallet_config", json.dumps(default_config, cls=I18nJSONEncoder), dict)
