from django.core.validators import RegexValidator

# The university issues 8-digit numeric registration numbers (e.g. 12302221). Stored in
# StudentProfile.roll_number; the UI calls it "registration number".
REGISTRATION_NUMBER_MESSAGE = "Registration number must be exactly 8 digits, e.g. 12302221."
validate_registration_number = RegexValidator(r"^[0-9]{8}\Z", REGISTRATION_NUMBER_MESSAGE)
