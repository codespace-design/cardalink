from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView

from .forms import EstateRegistrationForm
from .forms import HarvestBatchForm
from .models import Estate
from .models import EstatePhoto
from .models import HarvestBatch


class EstateListView(ListView):
    model = Estate
    template_name = "estates/estate_list.html"
    context_object_name = "estates"
    paginate_by = 12

    def get_queryset(self):
        qs = Estate.objects.select_related("owner").prefetch_related("photos").all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(owner_name__icontains=q)
                | Q(location__icontains=q)
                | Q(address__icontains=q)
            )
        filter_my = self.request.GET.get("filter", "")
        if filter_my == "mine" and self.request.user.is_authenticated:
            qs = qs.filter(owner=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        context["filter_my"] = self.request.GET.get("filter", "")
        if self.request.user.is_authenticated:
            context["my_estates_count"] = Estate.objects.filter(owner=self.request.user).count()
        return context


class EstateDetailView(DetailView):
    model = Estate
    template_name = "estates/estate_detail.html"
    context_object_name = "estate"

    def get_queryset(self):
        return (
            Estate.objects.select_related("owner")
            .prefetch_related("photos", "harvest_batches")
            .all()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated:
            role = getattr(user, "role", None)
            if role == "ADMIN":
                context["base_template"] = "users/admin_base.html"
            elif role == "SELLER":
                context["base_template"] = "users/seller_base.html"
            elif role == "BUYER":
                context["base_template"] = "users/buyer_base.html"
            else:
                context["base_template"] = "users/dashboard_base.html"
        else:
            context["base_template"] = "base.html"
        return context


class EstateCreateView(View):
    """
    Decommissioned standalone estate registration.
    Redirects users role-sensitively to their unified portals:
    - Sellers to /seller/estates/
    - Admins to /admin-dashboard/users/create/
    - Buyers to /buyer-dashboard/
    - Guests to /register/seller/
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("register_seller")

        user_role = getattr(request.user, "role", None)
        if user_role == "SELLER":
            messages.info(request, _("Please manage and register your estates directly from your Seller Portal."))
            return redirect("seller_estates")
        elif user_role == "ADMIN":
            messages.info(request, _("Register cardamom plantations directly via Manual User Registration."))
            return redirect("admin_user_create")
        elif user_role == "BUYER":
            return redirect("buyer_dashboard")

        return redirect("seller_estates")


class EstateUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Estate
    form_class = EstateRegistrationForm
    template_name = "estates/estate_form.html"

    def test_func(self):
        estate = self.get_object()
        return (
            self.request.user == estate.owner
            or self.request.user.is_staff
            or self.request.user.is_superuser
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        estate = form.save(commit=True)

        # Handle additional gallery photos if uploaded
        photos = self.request.FILES.getlist("photos")
        photo_count = 0
        for photo_file in photos:
            EstatePhoto.objects.create(
                estate=estate,
                image=photo_file,
                caption=f"Photo of {estate.name}",
            )
            photo_count += 1

        messages.success(
            self.request,
            _(
                f"Estate '{estate.name}' details updated successfully! "
                + (f"Added {photo_count} new photo(s)." if photo_count else "")
            ),
        )
        return redirect(estate.get_absolute_url())


class EstateDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Estate
    template_name = "estates/estate_confirm_delete.html"
    success_url = reverse_lazy("estates:list")

    def test_func(self):
        estate = self.get_object()
        return (
            self.request.user == estate.owner
            or self.request.user.is_staff
            or self.request.user.is_superuser
        )

    def form_valid(self, form):
        estate = self.get_object()
        messages.success(self.request, _(f"Estate '{estate.name}' was successfully deleted."))
        return super().form_valid(form)


class EstatePhotoDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        photo = get_object_or_404(EstatePhoto, pk=self.kwargs["photo_pk"], estate_id=self.kwargs["estate_pk"])
        return (
            self.request.user == photo.estate.owner
            or self.request.user.is_staff
            or self.request.user.is_superuser
        )

    def post(self, request, estate_pk, photo_pk):
        photo = get_object_or_404(EstatePhoto, pk=photo_pk, estate_id=estate_pk)
        estate = photo.estate
        photo.delete()
        messages.success(request, _("Gallery photo deleted successfully."))
        next_url = request.POST.get("next") or estate.get_absolute_url()
        return redirect(next_url)


class HarvestBatchCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = HarvestBatch
    form_class = HarvestBatchForm
    template_name = "estates/harvest_batch_form.html"

    def get_estate(self):
        return get_object_or_404(Estate, pk=self.kwargs["estate_pk"])

    def test_func(self):
        estate = self.get_estate()
        return (
            self.request.user == estate.owner
            or self.request.user.is_staff
            or self.request.user.is_superuser
            or getattr(self.request.user, "role", None) == "ADMIN"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estate = self.get_estate()
        context["estate"] = estate
        user = self.request.user
        if user.is_authenticated:
            role = getattr(user, "role", None)
            if role == "ADMIN":
                context["base_template"] = "users/admin_base.html"
            elif role == "SELLER":
                context["base_template"] = "users/seller_base.html"
            else:
                context["base_template"] = "users/dashboard_base.html"
        else:
            context["base_template"] = "base.html"
        return context

    def form_valid(self, form):
        estate = self.get_estate()
        batch = form.save(commit=False)
        batch.estate = estate
        batch.save()
        messages.success(
            self.request,
            _(f"Harvest batch of {batch.weight_kg} kg ({batch.get_grade_display()}) successfully logged for '{estate.name}'!"),
        )
        if getattr(self.request.user, "role", None) == "ADMIN":
            return redirect("admin_estate_detail", pk=estate.pk)
        return redirect(estate.get_absolute_url())


class HarvestBatchUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = HarvestBatch
    form_class = HarvestBatchForm
    template_name = "estates/harvest_batch_form.html"

    def test_func(self):
        batch = self.get_object()
        return (
            self.request.user == batch.estate.owner
            or self.request.user.is_staff
            or self.request.user.is_superuser
            or getattr(self.request.user, "role", None) == "ADMIN"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estate = self.get_object().estate
        context["estate"] = estate
        user = self.request.user
        if user.is_authenticated:
            role = getattr(user, "role", None)
            if role == "ADMIN":
                context["base_template"] = "users/admin_base.html"
            elif role == "SELLER":
                context["base_template"] = "users/seller_base.html"
            else:
                context["base_template"] = "users/dashboard_base.html"
        else:
            context["base_template"] = "base.html"
        return context

    def form_valid(self, form):
        batch = form.save()
        messages.success(
            self.request,
            _(f"Harvest batch #{batch.id} details updated successfully!"),
        )
        if getattr(self.request.user, "role", None) == "ADMIN":
            return redirect("admin_estate_detail", pk=batch.estate.pk)
        return redirect(batch.estate.get_absolute_url())


class HarvestBatchDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = HarvestBatch
    template_name = "estates/harvest_batch_confirm_delete.html"

    def test_func(self):
        batch = self.get_object()
        return (
            self.request.user == batch.estate.owner
            or self.request.user.is_staff
            or self.request.user.is_superuser
            or getattr(self.request.user, "role", None) == "ADMIN"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estate = self.get_object().estate
        context["estate"] = estate
        user = self.request.user
        if user.is_authenticated:
            role = getattr(user, "role", None)
            if role == "ADMIN":
                context["base_template"] = "users/admin_base.html"
            elif role == "SELLER":
                context["base_template"] = "users/seller_base.html"
            else:
                context["base_template"] = "users/dashboard_base.html"
        else:
            context["base_template"] = "base.html"
        return context

    def get_success_url(self):
        if getattr(self.request.user, "role", None) == "ADMIN":
            return reverse_lazy("admin_estate_detail", kwargs={"pk": self.get_object().estate.pk})
        return self.get_object().estate.get_absolute_url()

    def form_valid(self, form):
        batch = self.get_object()
        estate = batch.estate
        messages.success(
            self.request,
            _(f"Harvest batch #{batch.id} ({batch.weight_kg} kg) deleted successfully from '{estate.name}'."),
        )
        return super().form_valid(form)


estate_list_view = EstateListView.as_view()
estate_detail_view = EstateDetailView.as_view()
estate_create_view = EstateCreateView.as_view()
estate_update_view = EstateUpdateView.as_view()
estate_delete_view = EstateDeleteView.as_view()
estate_photo_delete_view = EstatePhotoDeleteView.as_view()
harvest_batch_create_view = HarvestBatchCreateView.as_view()
harvest_batch_update_view = HarvestBatchUpdateView.as_view()
harvest_batch_delete_view = HarvestBatchDeleteView.as_view()
