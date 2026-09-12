import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ComplexPasswordValidator:
    """
    Validates that a password fulfills professional complexity requirements:
    - Minimum length of 8 characters
    - At least one letter (a-z, A-Z)
    - At least one numeric digit (0-9)
    - At least one special symbol
    """

    def __init__(self, min_length: int = 8):
        self.min_length = min_length

    def validate(self, password: str, user=None):
        errors = []

        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    _(f"Password must be at least {self.min_length} characters long."),
                    code="password_too_short",
                )
            )

        if not re.search(r"[a-zA-Z]", password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one letter (a-z, A-Z)."),
                    code="password_no_letter",
                )
            )

        if not re.search(r"[0-9]", password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one numeric digit (0-9)."),
                    code="password_no_number",
                )
            )

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one special symbol (e.g., !@#$%^&*)."),
                    code="password_no_symbol",
                )
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            f"Your password must be at least {self.min_length} characters long and contain "
            "at least one letter, one number, and one special symbol."
        )
