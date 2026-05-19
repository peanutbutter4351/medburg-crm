# core/importers/__init__.py
#
# Public surface of the importers package.
# Concrete importers (DoctorImporter, MedicineImporter, …) are not exposed
# here — callers import them directly from their own modules.
# Only the reusable foundation types are re-exported so consuming code
# can write:
#
#   from core.importers import BaseExcelImporter, ImportResult
#
from core.importers.base_importer import BaseExcelImporter, ImportResult

__all__ = [
    "BaseExcelImporter",
    "ImportResult",
]
