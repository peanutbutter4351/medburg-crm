from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import path


class ExcelUploadForm(forms.Form):
    """Secure form for Excel file uploads."""

    excel_file = forms.FileField(
        label="Select an Excel file (.xlsx)",
        help_text="Only .xlsx files are supported."
    )

    def clean_excel_file(self):
        file = self.cleaned_data.get("excel_file")
        if file:
            if not file.name.lower().endswith(".xlsx"):
                raise forms.ValidationError("Invalid file type. Please upload a .xlsx file.")
        return file


class ExcelImportAdminMixin:
    """
    Mixin for Django ModelAdmin to add a production-grade 'Import from Excel' workflow.
    Keeps upload flow, security, and messaging reusable across any app (e.g. Medicine, Pricing).

    Subclasses MUST define:
    - importer_class: The ExcelImporter class (e.g., DoctorImporter).
    """

    change_list_template = "admin/excel_import_changelist.html"
    importer_class = None

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        if request.method == "POST":
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = form.cleaned_data["excel_file"]
                try:
                    importer = self.importer_class()
                    result = importer.import_file(excel_file)

                    # Determine and show flash message
                    if result.error_count == 0 and result.skipped == 0:
                        messages.success(request, result.summary())
                    elif result.imported > 0:
                        messages.warning(request, f"Partial success: {result.summary()}")
                    else:
                        messages.error(request, f"Import failed: {result.summary()}")

                except Exception as exc:
                    messages.error(request, f"Catastrophic failure during import: {str(exc)}")

                return redirect(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist")
        else:
            form = ExcelUploadForm()

        context = {
            "title": f"Import {self.model._meta.verbose_name_plural} from Excel",
            "form": form,
            "opts": self.model._meta,
            **self.admin_site.each_context(request),
        }
        return render(request, "admin/excel_import_form.html", context)
