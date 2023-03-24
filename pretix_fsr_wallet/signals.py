import json
from django.dispatch import receiver
from i18nfield.utils import I18nJSONEncoder
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import register_payment_providers

from .payment import Wallet


@receiver(register_payment_providers, dispatch_uid="payment_wallet")
def register_payment_provider(sender, **kwargs):
    return [Wallet]


default_config = {
    "wallet_backend:url": "https://api.wallet.myhpi.de",
    "oidc:url": "https://oidc.hpi.de",
}

settings_hierarkey.add_default(
    "fsr_wallet_config", json.dumps(default_config, cls=I18nJSONEncoder), dict
)
