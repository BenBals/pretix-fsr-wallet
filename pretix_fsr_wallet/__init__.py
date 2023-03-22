from django.utils.translation import gettext_lazy
from pathlib import Path

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")

__version__ = "1.0.0"


class PluginApp(PluginConfig):
    name = "pretix_fsr_wallet"
    verbose_name = "VerDE Wallet"

    class PretixPluginMeta:
        name = gettext_lazy("VerDE Wallet")
        author = "Ben Bals"
        description = gettext_lazy("Custom payment provider for wallet.myhpi.de, built for the FSR Digital Engineering at Uni Potsdam")
        visible = True
        version = __version__
        category = "PAYMENT"
        compatibility = "pretix>=3.18.0.dev0"

    def ready(self):
        script_path = Path( __file__ ).absolute()
        print("Running fsr wallet ready from ", script_path)
        from . import signals  # NOQA


default_app_config = "pretix_fsr_wallet.PluginApp"
