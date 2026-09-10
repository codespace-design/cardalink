import io
from decimal import Decimal
from PIL import Image

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from carda_link.estates.forms import EstateRegistrationForm
from carda_link.estates.forms import HarvestBatchForm
from carda_link.estates.models import Estate
from carda_link.estates.models import EstatePhoto
from carda_link.estates.models import HarvestBatch

User = get_user_model()


def get_test_image():
    """Generate a small dummy image in memory."""
    file = io.BytesIO()
    image = Image.new("RGBA", size=(50, 50), color=(16, 185, 129))
    image.save(file, "png")
    file.name = "test_image.png"
    file.seek(0)
    return SimpleUploadedFile(file.name, file.read(), content_type="image/png")


class EstateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="grower@example.com",
            password="testpassword123",
            name="John Grower",
            phone_number="+91 98765 43210",
            address="Vandanmedu, Idukki",
            status="ACTIVE",
            role="SELLER",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpassword123",
            name="Other Grower",
            status="ACTIVE",
            role="SELLER",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_estate_creation(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Green Valley Cardamom Estate",
            owner_name="John Grower",
            phone_number="+91 98765 43210",
            address="Plot 42, Nedumkandam Road, Idukki",
            location="Nedumkandam, Idukki",
            area_in_acres=Decimal("15.50"),
            description="Premium Njallani variety cardamom estate.",
            primary_photo=get_test_image(),
        )
        self.assertEqual(str(estate), "Green Valley Cardamom Estate")
        self.assertEqual(estate.owner, self.user)
        self.assertEqual(estate.area_in_acres, Decimal("15.50"))
        self.assertTrue(bool(estate.primary_photo))
        self.assertEqual(estate.total_harvest_kg, Decimal("0"))

    def test_estate_photo_gallery(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Hilltop Cardamom Gardens",
            owner_name="John Grower",
            phone_number="+91 98765 43210",
            address="Vandanmedu, Idukki",
            location="Idukki, Kerala",
            area_in_acres=Decimal("20.00"),
        )
        photo1 = EstatePhoto.objects.create(
            estate=estate,
            image=get_test_image(),
            caption="Curing Chamber",
        )
        photo2 = EstatePhoto.objects.create(
            estate=estate,
            image=get_test_image(),
            caption="Cardamom Pods",
        )
        self.assertEqual(estate.photos.count(), 2)
        self.assertIn("Photo for Hilltop Cardamom Gardens", str(photo1))

    def test_estate_registration_form_initial_user_data(self):
        form = EstateRegistrationForm(user=self.user)
        self.assertEqual(form.initial.get("owner_name"), "John Grower")
        self.assertEqual(form.initial.get("phone_number"), "+91 98765 43210")
        self.assertEqual(form.initial.get("address"), "Vandanmedu, Idukki")

    def test_estate_registration_form_validation(self):
        data = {
            "name": "Sunrise Plantation",
            "owner_name": "John Grower",
            "phone_number": "+91 98765 43210",
            "address": "Santhanpara, Idukki",
            "location": "Santhanpara, Idukki",
            "area_in_acres": "12.00",
            "description": "High altitude spice plantation",
        }
        form = EstateRegistrationForm(data=data, user=self.user)
        self.assertTrue(form.is_valid())

        invalid_data = data.copy()
        invalid_data["area_in_acres"] = "0"
        invalid_form = EstateRegistrationForm(data=invalid_data, user=self.user)
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("area_in_acres", invalid_form.errors)

    def test_estate_register_view_get(self):
        response = self.client.get(reverse("estates:register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register Your Cardamom Estate")
        self.assertContains(response, "Estate & Owner Profile")
        self.assertContains(response, "Estate / Plantation Name")

    def test_estate_register_view_post_with_photos(self):
        primary_img = get_test_image()
        gallery_img_1 = get_test_image()
        gallery_img_2 = get_test_image()

        post_data = {
            "name": "Highland Green Plantation",
            "owner_name": "John Grower",
            "phone_number": "+91 98470 12345",
            "address": "Munnar Road, Nedumkandam, Idukki",
            "location": "Nedumkandam, Idukki",
            "area_in_acres": "18.75",
            "description": "Organic certified cardamom plantation.",
            "primary_photo": primary_img,
            "photos": [gallery_img_1, gallery_img_2],
        }
        response = self.client.post(reverse("estates:register"), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        estate = Estate.objects.get(name="Highland Green Plantation")
        self.assertEqual(estate.owner, self.user)
        self.assertEqual(estate.owner_name, "John Grower")
        self.assertEqual(estate.phone_number, "+91 98470 12345")
        self.assertEqual(estate.address, "Munnar Road, Nedumkandam, Idukki")
        self.assertEqual(estate.photos.count(), 2)
        self.assertTrue(bool(estate.primary_photo))

    def test_estate_list_view(self):
        Estate.objects.create(
            owner=self.user,
            name="Estate Alpha",
            owner_name="John",
            phone_number="12345",
            address="Address Alpha",
            location="Idukki",
            area_in_acres=Decimal("10.00"),
        )
        response = self.client.get(reverse("estates:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estate Alpha")

    def test_estate_detail_view(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Estate Beta",
            owner_name="John",
            phone_number="+91 98765 43210",
            address="Address Beta",
            location="Nedumkandam",
            area_in_acres=Decimal("25.00"),
            description="Special detailed description",
        )
        response = self.client.get(reverse("estates:detail", kwargs={"pk": estate.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estate Beta")
        self.assertContains(response, "+91 98765 43210")
        self.assertContains(response, "Address Beta")
        self.assertContains(response, "Special detailed description")

    def test_estate_update_view(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Estate Gamma",
            owner_name="John",
            phone_number="+91 98765 43210",
            address="Address Gamma",
            location="Idukki",
            area_in_acres=Decimal("15.00"),
        )
        response = self.client.post(
            reverse("estates:update", kwargs={"pk": estate.pk}),
            data={
                "name": "Estate Gamma Updated",
                "owner_name": "John Updated",
                "phone_number": "+91 98765 43210",
                "address": "Address Gamma",
                "location": "Idukki",
                "area_in_acres": "16.00",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        estate.refresh_from_db()
        self.assertEqual(estate.name, "Estate Gamma Updated")
        self.assertEqual(estate.area_in_acres, Decimal("16.00"))

    def test_estate_delete_view(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Estate Delta To Delete",
            owner_name="John",
            phone_number="12345",
            address="Address Delta",
            location="Idukki",
            area_in_acres=Decimal("5.00"),
        )
        # GET delete confirm page
        response = self.client.get(reverse("estates:delete", kwargs={"pk": estate.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Estate?")

        # POST delete
        response = self.client.post(reverse("estates:delete", kwargs={"pk": estate.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Estate.objects.filter(pk=estate.pk).exists())

    def test_estate_unauthorized_edit_delete(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Estate Protected",
            owner_name="John",
            phone_number="12345",
            address="Address",
            location="Idukki",
            area_in_acres=Decimal("5.00"),
        )
        # Login as other user
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("estates:update", kwargs={"pk": estate.pk}))
        self.assertEqual(response.status_code, 403)

        del_response = self.client.post(reverse("estates:delete", kwargs={"pk": estate.pk}))
        self.assertEqual(del_response.status_code, 403)

    def test_estate_photo_delete_view(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Estate Photo Test",
            owner_name="John",
            phone_number="12345",
            address="Address",
            location="Idukki",
            area_in_acres=Decimal("10.00"),
        )
        photo = EstatePhoto.objects.create(
            estate=estate,
            image=get_test_image(),
            caption="Photo to delete",
        )
        self.assertEqual(estate.photos.count(), 1)

        response = self.client.post(
            reverse("estates:photo-delete", kwargs={"estate_pk": estate.pk, "photo_pk": photo.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(estate.photos.count(), 0)

    def test_harvest_batch_crud(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="Estate Harvest Test",
            owner_name="John",
            phone_number="12345",
            address="Address",
            location="Idukki",
            area_in_acres=Decimal("10.00"),
        )

        # GET create harvest batch page
        response = self.client.get(reverse("estates:harvest-create", kwargs={"estate_pk": estate.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log New Harvest Batch")

        # POST create harvest batch
        create_data = {
            "harvest_date": "2026-08-15",
            "weight_kg": "350.50",
            "grade": "AGEB",
        }
        response = self.client.post(
            reverse("estates:harvest-create", kwargs={"estate_pk": estate.pk}),
            data=create_data,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(estate.harvest_batches.count(), 1)
        batch = estate.harvest_batches.first()
        self.assertEqual(batch.weight_kg, Decimal("350.50"))
        self.assertEqual(batch.grade, "AGEB")
        self.assertEqual(estate.total_harvest_kg, Decimal("350.50"))

        # Edit harvest batch
        update_data = {
            "harvest_date": "2026-08-15",
            "weight_kg": "400.00",
            "grade": "AGB",
        }
        response = self.client.post(
            reverse("estates:harvest-update", kwargs={"pk": batch.pk}),
            data=update_data,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        batch.refresh_from_db()
        self.assertEqual(batch.weight_kg, Decimal("400.00"))
        self.assertEqual(batch.grade, "AGB")

        # Delete harvest batch
        del_confirm_response = self.client.get(reverse("estates:harvest-delete", kwargs={"pk": batch.pk}))
        self.assertEqual(del_confirm_response.status_code, 200)
        self.assertContains(del_confirm_response, "Delete Harvest Batch?")

        del_response = self.client.post(reverse("estates:harvest-delete", kwargs={"pk": batch.pk}), follow=True)
        self.assertEqual(del_response.status_code, 200)
        self.assertEqual(estate.harvest_batches.count(), 0)

    def test_harvest_batch_form_validation(self):
        # Valid form
        form = HarvestBatchForm(data={"harvest_date": "2026-08-10", "weight_kg": "120.00", "grade": "AGEB"})
        self.assertTrue(form.is_valid())

        # Invalid weight (<= 0)
        invalid_form = HarvestBatchForm(data={"harvest_date": "2026-08-10", "weight_kg": "0", "grade": "AGEB"})
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("weight_kg", invalid_form.errors)

    def test_ninja_api_estates_and_batches(self):
        estate = Estate.objects.create(
            owner=self.user,
            name="API Test Estate",
            owner_name="John",
            phone_number="12345",
            address="Address",
            location="Idukki",
            area_in_acres=Decimal("12.00"),
        )
        # GET /api/estates/
        response = self.client.get("/api/estates/")
        self.assertEqual(response.status_code, 200)

        # GET /api/estates/{id}
        response = self.client.get(f"/api/estates/{estate.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "API Test Estate")

        # POST /api/estates/{id}/batches
        batch_payload = {
            "harvest_date": "2026-08-10",
            "weight_kg": 200.0,
            "grade": "AGEB",
        }
        response = self.client.post(
            f"/api/estates/{estate.pk}/batches",
            data=batch_payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        batch_id = response.json()["id"]

        # GET /api/estates/{id}/batches
        response = self.client.get(f"/api/estates/{estate.pk}/batches")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        # DELETE /api/estates/batches/{batch_id}
        response = self.client.delete(f"/api/estates/batches/{batch_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(estate.harvest_batches.count(), 0)
