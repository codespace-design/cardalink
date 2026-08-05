from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuctionsConfig(AppConfig):
    name = "carda_link.auctions"
    verbose_name = _("Auctions & Marketplace")
