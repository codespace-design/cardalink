from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InvoicingConfig(AppConfig):
    name = "carda_link.invoicing"
    verbose_name = _("Invoicing & Financial Transactions")
