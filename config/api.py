from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI
from ninja.security import SessionAuth


class CustomSessionAuth(SessionAuth):
    def authenticate(self, request, key):
        if request.user and request.user.is_authenticated:
            return request.user
        return None


api = NinjaAPI(
    urls_namespace="api",
    auth=CustomSessionAuth(),
    docs_decorator=staff_member_required,
)

api.add_router("/users/", "carda_link.users.api.views.router")
api.add_router("/estates/", "carda_link.estates.api.router")
api.add_router(
    "/auctions/",
    "carda_link.auctions.api.router",
)
api.add_router(
    "/invoicing/",
    "carda_link.invoicing.api.router",
)
api.add_router(
    "/assistant/",
    "carda_link.assistant.api.router",
)
