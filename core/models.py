"""
Core models for the Medburg CRM.

BaseModel  — abstract base with created_at / updated_at timestamps.
ImportLog  — audit record for every Excel import operation.
"""

from django.db import models


class BaseModel(models.Model):
    """Abstract base with created / updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


# ─────────────────────────────────────────────────────────────────────────────
# ImportLog
# ─────────────────────────────────────────────────────────────────────────────

class ImportLog(BaseModel):
    """
    Audit record created for every Excel import attempt.

    One row per import job — regardless of whether it succeeded, partially
    succeeded, or failed completely.  Provides a full operational history
    visible in Django admin and queryable for dashboards / alerting.

    Inherits from BaseModel:
        created_at  — when the import was triggered (auto, indexed)
        updated_at  — last status update (auto)

    Design notes
    ────────────
    - import_type uses a bounded choice set so the admin filter sidebar works
      out of the box and typos are caught at the model layer.
    - error_log is TextField (not JSONField) so it renders plainly in admin
      without a plugin and works identically on PostgreSQL and SQLite (dev).
      Structured error data lives in ImportResult; this field stores the
      human-readable summary produced by ImportResult.summary() plus any
      per-row RowError strings the caller chooses to append.
    - success_rows + failed_rows may not sum to total_rows when the import
      was aborted mid-stream (status=FAILED before all rows were processed).
    """

    # ── Import type choices ───────────────────────────────────────────────────
    TYPE_DOCTOR   = "doctor"
    TYPE_MEDICINE = "medicine"
    TYPE_PRICING  = "pricing"

    IMPORT_TYPE_CHOICES = [
        (TYPE_DOCTOR,   "Doctor Import"),
        (TYPE_MEDICINE, "Medicine Import"),
        (TYPE_PRICING,  "Pricing Import"),
    ]

    # ── Status choices ────────────────────────────────────────────────────────
    STATUS_PENDING  = "pending"    # job queued, not yet started
    STATUS_SUCCESS  = "success"    # all rows imported without errors
    STATUS_PARTIAL  = "partial"    # some rows imported, some had errors
    STATUS_FAILED   = "failed"     # structural failure (bad file, missing headers)

    STATUS_CHOICES = [
        (STATUS_PENDING,  "Pending"),
        (STATUS_SUCCESS,  "Success"),
        (STATUS_PARTIAL,  "Partial"),
        (STATUS_FAILED,   "Failed"),
    ]

    # ── Fields ────────────────────────────────────────────────────────────────

    import_type = models.CharField(
        max_length=20,
        choices=IMPORT_TYPE_CHOICES,
        db_index=True,
        help_text="Category of data being imported.",
    )
    file_name = models.CharField(
        max_length=255,
        help_text="Original filename as uploaded by the user.",
    )
    total_rows = models.PositiveIntegerField(
        default=0,
        help_text="Total data rows seen in the file (header row excluded).",
    )
    success_rows = models.PositiveIntegerField(
        default=0,
        help_text="Rows successfully written to the database.",
    )
    failed_rows = models.PositiveIntegerField(
        default=0,
        help_text="Rows that failed validation or DB write.",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text="Overall outcome of the import job.",
    )
    error_log = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Human-readable summary of errors encountered during the import. "
            "Populated from ImportResult.summary() and per-row RowError strings."
        ),
    )

    # ── Meta ──────────────────────────────────────────────────────────────────

    class Meta(BaseModel.Meta):
        verbose_name      = "Import Log"
        verbose_name_plural = "Import Logs"
        # Inherit BaseModel ordering: newest first (-created_at)

    # ── Representation ────────────────────────────────────────────────────────

    def __str__(self) -> str:
        # e.g. "Doctor Import — doctors_may2026.xlsx (success)"
        return (
            f"{self.get_import_type_display()} — "
            f"{self.file_name} "
            f"({self.get_status_display()})"
        )

    # ── Convenience helpers ───────────────────────────────────────────────────

    @property
    def skipped_rows(self) -> int:
        """Rows neither imported nor failed (e.g. duplicates, empty rows)."""
        return max(0, self.total_rows - self.success_rows - self.failed_rows)

    @classmethod
    def from_result(
        cls,
        import_type: str,
        file_name: str,
        result: "ImportResult",  # noqa: F821 — avoids circular import
    ) -> "ImportLog":
        """
        Factory: build and save an ImportLog from an ImportResult object.

        Usage in a concrete importer view or service:

            from core.importers import ImportResult
            from core.models import ImportLog

            result = DoctorImporter().import_file(uploaded_file)
            log = ImportLog.from_result(
                import_type=ImportLog.TYPE_DOCTOR,
                file_name=uploaded_file.name,
                result=result,
            )

        The log is saved to the database before being returned.
        """
        # Determine overall status from the result
        if result.error_count == 0:
            status = cls.STATUS_SUCCESS
        elif result.imported > 0:
            status = cls.STATUS_PARTIAL
        else:
            status = cls.STATUS_FAILED

        # Build the human-readable error log text
        error_lines = [result.summary()]
        if result.errors:
            error_lines.append("")  # blank separator
            error_lines.extend(str(e) for e in result.errors)
        error_text = "\n".join(error_lines)

        log = cls(
            import_type=import_type,
            file_name=file_name,
            total_rows=result.total_rows,
            success_rows=result.imported,
            failed_rows=result.error_count,
            status=status,
            error_log=error_text,
        )
        log.save()
        return log
