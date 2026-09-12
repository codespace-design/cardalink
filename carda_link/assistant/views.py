from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def chatbot(request):
    return render(request, "assistant/chatbot.html")