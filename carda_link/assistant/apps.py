from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AssistantConfig(AppConfig):
    name = "carda_link.assistant"
    verbose_name = _("AI Agricultural Assistant & Analytics")
