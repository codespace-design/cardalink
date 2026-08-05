from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EstatesConfig(AppConfig):
    name = "carda_link.estates"
    verbose_name = _("Estates & Farm Management")
