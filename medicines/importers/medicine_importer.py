import re
from typing import Any, Optional

from django.db import transaction

from core.importers.base_importer import BaseExcelImporter, ImportResult, RowError
from core.models import ImportLog
from doctors.importers.doctor_importer import AuditedExcelImporterMixin
from medicines.models import Medicine


class MedicineImporter(AuditedExcelImporterMixin, BaseExcelImporter):
    """
    Production-grade importer for Medicine catalogue.
    Features UPSERT functionality to handle daily/weekly price list updates
    from distributors efficiently without breaking Doctor mappings.
    """

    REQUIRED_HEADERS = ["Medicine Name", "PTR", "PTS", "MRP"]
    import_type = ImportLog.TYPE_MEDICINE

    def __init__(self) -> None:
        super().__init__()
        # Pre-cache: (lower_name, lower_brand) -> medicine_id
        # Provides O(1) in-memory duplicate detection for rapid UPSERTing
        self._existing_medicines: dict[tuple[str, str], int] = {}

    def import_file(self, file_path_or_buffer: Any) -> ImportResult:
        """Override to precache existing medicines for efficient upserts."""
        for med_id, med_name, med_brand in Medicine.objects.values_list("id", "name", "brand"):
            n_key = med_name.strip().lower() if med_name else ""
            b_key = med_brand.strip().lower() if med_brand else ""
            self._existing_medicines[(n_key, b_key)] = med_id

        # Continues with standard workflow, hitting AuditedExcelImporterMixin next
        return super().import_file(file_path_or_buffer)

    def _parse_currency(self, raw_val: str) -> Optional[float]:
        """Safely extract float from strings like '  ₹ 1,200.50  '."""
        if not raw_val:
            return None
        
        # Remove everything except digits and decimal point
        cleaned = re.sub(r"[^\d.]", "", raw_val)
        if not cleaned:
            return None
            
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _validate_row(self, row_num: int, row: dict[str, Any]) -> list[RowError]:
        errors = []

        name = self._cell(row, "Medicine Name")
        if not name:
            errors.append(self._err(row_num, "Medicine Name", "Medicine Name is required."))

        ptr = self._parse_currency(self._cell(row, "PTR"))
        pts = self._parse_currency(self._cell(row, "PTS"))
        mrp = self._parse_currency(self._cell(row, "MRP"))

        if ptr is None:
            errors.append(self._err(row_num, "PTR", "Valid numerical PTR is required."))
        if pts is None:
            errors.append(self._err(row_num, "PTS", "Valid numerical PTS is required."))
        if mrp is None:
            errors.append(self._err(row_num, "MRP", "Valid numerical MRP is required."))

        if ptr is not None and pts is not None and mrp is not None:
            # Business Logic: Enforce MRP >= PTR >= PTS
            if not (mrp >= ptr >= pts):
                errors.append(
                    self._err(
                        row_num,
                        "Pricing Logic",
                        f"Pricing violation: Expected MRP ({mrp}) >= PTR ({ptr}) >= PTS ({pts})."
                    )
                )

        return errors

    def _import_row(self, row_num: int, row: dict[str, Any], result: ImportResult) -> None:
        name = self._cell(row, "Medicine Name")
        brand = self._cell(row, "Brand Name")
        
        # Normalize blank brand to empty string to satisfy NOT NULL constraint
        brand_val = brand.strip() if brand else ""

        ptr = self._parse_currency(self._cell(row, "PTR"))
        pts = self._parse_currency(self._cell(row, "PTS"))
        mrp = self._parse_currency(self._cell(row, "MRP"))

        name_key = name.lower()
        brand_key = brand.lower() if brand else ""

        defaults = {
            "ptr": ptr,
            "pts": pts,
            "mrp": mrp,
        }

        # Transactional UPSERT operation
        with transaction.atomic():
            if (name_key, brand_key) in self._existing_medicines:
                # Medicine exists -> Update pricing safely
                med_id = self._existing_medicines[(name_key, brand_key)]
                Medicine.objects.filter(id=med_id).update(**defaults)
                result.imported += 1
            else:
                # Medicine does not exist -> Create it
                new_med = Medicine.objects.create(name=name, brand=brand_val, **defaults)
                
                # Update in-memory cache to prevent file-internal duplication 
                # (if the same medicine appears twice in the same Excel sheet)
                self._existing_medicines[(name_key, brand_key)] = new_med.id
                result.imported += 1

