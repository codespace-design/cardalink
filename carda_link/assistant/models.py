from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class CultivationGuideline(models.Model):
    title = models.CharField(_("Guideline Title"), max_length=255)
    category = models.CharField(_("Category"), max_length=100, default="Pest Control")
    content = models.TextField(_("Guideline Content"))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ChatQueryLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_queries")
    query_text = models.TextField(_("Query Text"))
    response_text = models.TextField(_("AI Response"))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Query by {self.user} at {self.created_at}"
