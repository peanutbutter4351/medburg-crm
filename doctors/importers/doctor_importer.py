from typing import Any

from django.db import transaction

from core.constants import DOCTOR_MODE_CHOICES, DOCTOR_TYPE_CHOICES
from core.importers.base_importer import BaseExcelImporter, ImportResult, RowError
from doctors.models import Doctor


class DoctorImporter(BaseExcelImporter):
    """
    Importer for Doctor records via Excel.
    Provides scalable row processing, normalization, and duplicate detection.
    """

    REQUIRED_HEADERS = ["Doctor Name"]

    def __init__(self) -> None:
        super().__init__()
        # Cache for duplicate detection: set of (lowercase_name, lowercase_location)
        # Preloaded in import_file() to avoid per-row DB queries.
        self._existing_doctors: set[tuple[str, str]] = set()

    def import_file(self, file_path_or_buffer: Any) -> ImportResult:
        """Override to precache existing doctors for efficient duplicate detection."""
        for doc_name, doc_loc in Doctor.objects.values_list("name", "location"):
            name_key = doc_name.strip().lower() if doc_name else ""
            loc_key = doc_loc.strip().lower() if doc_loc else ""
            self._existing_doctors.add((name_key, loc_key))

        # Continue with standard BaseExcelImporter workflow
        return super().import_file(file_path_or_buffer)

    def _validate_row(self, row_num: int, row: dict[str, Any]) -> list[RowError]:
        errors = []

        name = self._cell(row, "Doctor Name")
        if not name:
            errors.append(self._err(row_num, "Doctor Name", "Doctor Name is required."))

        mode = self._cell(row, "Doctor Mode")
        if mode:
            mode_lower = mode.lower()
            valid_modes = [choice[0] for choice in DOCTOR_MODE_CHOICES]
            if mode_lower not in valid_modes:
                errors.append(
                    self._err(
                        row_num,
                        "Doctor Mode",
                        f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
                    )
                )

        doc_type = self._cell(row, "Doctor Type")
        if doc_type:
            type_lower = doc_type.lower()
            valid_types = [choice[0] for choice in DOCTOR_TYPE_CHOICES]
            if type_lower not in valid_types:
                errors.append(
                    self._err(
                        row_num,
                        "Doctor Type",
                        f"Invalid type. Must be one of: {', '.join(valid_types)}",
                    )
                )

        return errors

    def _import_row(self, row_num: int, row: dict[str, Any], result: ImportResult) -> None:
        name = self._cell(row, "Doctor Name")
        phone = self._cell(row, "Phone Number") or None
        
        email = self._cell(row, "Email")
        if email:
            email = email.lower() or None
            
        specialization = self._cell(row, "Specialization") or None
        hospital = self._cell(row, "Hospital / Clinic")
        location = self._cell(row, "Location / City")
        mode = self._cell(row, "Doctor Mode")
        doc_type = self._cell(row, "Doctor Type")

        name_key = name.lower()
        loc_key = location.lower()

        # 1. Efficient In-Memory Duplicate Detection
        if (name_key, loc_key) in self._existing_doctors:
            result.skipped += 1
            result.add_error(
                row_num,
                "Doctor Name",
                f"Duplicate doctor skipped (Name: '{name}', Location: '{location}')."
            )
            return

        # Register this row to prevent duplicates *within* the same Excel file
        self._existing_doctors.add((name_key, loc_key))

        # 2. Build payload
        kwargs = {
            "name": name,
            "phone_number": phone,
            "email": email,
            "specialization": specialization,
            "hospital": hospital,
            "location": location,
        }
        
        if mode:
            kwargs["mode"] = mode.lower()
        if doc_type:
            kwargs["doctor_type"] = doc_type.lower()

        # 3. Transactional Save
        with transaction.atomic():
            Doctor.objects.create(**kwargs)
            result.imported += 1
