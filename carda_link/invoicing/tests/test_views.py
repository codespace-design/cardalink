from decimal import Decimal
import pytest
from django.urls import reverse
from carda_link.invoicing.models import Invoice
from carda_link.auctions.models import Lot

pytestmark = pytest.mark.django_db


def test_invoice_list_view(client):
    url = reverse("invoicing:list")
    response = client.get(url)
    assert response.status_code == 200
    assert "invoices" in response.context
    assert "total_invoices" in response.context


def test_confirm_bidding_view_get(client):
    url = reverse("invoicing:confirm")
    response = client.get(url)
    assert response.status_code == 200
    assert "form" in response.context


def test_confirm_bidding_view_post(client):
    # Ensure demo data is seeded
    client.get(reverse("invoicing:list"))

    lot = Lot.objects.filter(is_sold=False).first()
    if not lot:
        lot = Lot.objects.first()

    url = reverse("invoicing:confirm")
    post_data = {
        "lot": lot.id,
        "winning_bid_per_kg": "2600.00",
        "commission_percentage": "2.0",
    }
    response = client.post(url, post_data)
    assert response.status_code == 302

    # Check invoice was updated/created
    invoice = Invoice.objects.get(lot=lot)
    assert invoice.status == "PENDING"
    assert invoice.total_amount > 0


def test_invoice_detail_view(client):
    # Ensure demo data is seeded
    client.get(reverse("invoicing:list"))
    invoice = Invoice.objects.first()

    url = reverse("invoicing:detail", kwargs={"pk": invoice.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["invoice"] == invoice
    assert "subtotal" in response.context


def test_invoice_pay_view(client):
    # Ensure demo data is seeded
    client.get(reverse("invoicing:list"))
    invoice = Invoice.objects.filter(status="PENDING").first()

    url = reverse("invoicing:pay", kwargs={"pk": invoice.pk})
    response = client.post(url)
    assert response.status_code == 302

    invoice.refresh_from_db()
    assert invoice.status == "PAID"
    assert invoice.paid_at is not None
