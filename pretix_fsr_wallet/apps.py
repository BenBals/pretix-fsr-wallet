from django.apps import AppConfig
from django.utils.translation import gettext_lazy
from . import __version__
from pathlib import Path


class PluginApp(AppConfig):
    name = 'pretix_fsr_wallet'
    verbose_name = 'VerDE Wallet'

    class PretixPluginMeta:
        name = gettext_lazy("VerDE Wallet")
        author = "Ben Bals"
        description = gettext_lazy(
            "[DEPRECATED] Custom payment provider for wallet.myhpi.de, built for the FSR Digital Engineering at Uni Potsdam"
        )
        visible = True
        version = __version__
        category = "PAYMENT"
        compatibility = "pretix>=4.20.0"


    def ready(self):
        script_path = Path( __file__ ).absolute()
        print("Running VerDE Wallet ready from ", script_path)
        from . import signals  # NOQA

default_app_config = "pretix_fsr_wallet.PluginApp"