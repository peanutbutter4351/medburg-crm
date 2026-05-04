"""
Report service layer.

All filtering, aggregation, and Excel export logic lives here so
views remain thin and templates receive pre-computed data only.

Performance
───────────
• select_related  — avoids N+1 on doctor / medicine / rep FKs
• DB-level annotation — value = quantity × medicine__ptr
• Aggregated summary uses the same pre-filtered queryset
• No Python loops for data computation
• Subquery-based aggregation for doctor-level ROI to avoid
  cross-join duplication between Investment and SalesEntry.
"""

from decimal import Decimal
from io import BytesIO

from django.db.models import (
    Case, CharField, F, Subquery, Sum, Value, When,
    DecimalField, OuterRef,
)
from django.db.models.functions import Coalesce

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from accounts.models import User
from core.constants import ROLE_REP
from doctors.models import Doctor, Investment
from medicines.models import Medicine
from sales.models import SalesEntry


# ─── Filter-option helpers ───────────────────────────────────────

def get_report_filter_options():
    """
    Return distinct values for every filter dropdown on the report page.
    """
    doctors = (
        Doctor.objects
        .filter(is_active=True)
        .order_by("name")
        .values("id", "name")
    )

    reps = (
        User.objects
        .filter(role=ROLE_REP, is_active=True)
        .order_by("first_name", "last_name")
        .values("id", "first_name", "last_name", "username")
    )

    medicines = (
        Medicine.objects
        .filter(is_active=True)
        .order_by("name")
        .values("id", "name", "brand")
    )

    return {
        "doctors": list(doctors),
        "reps": list(reps),
        "medicines": list(medicines),
    }


# ─── Core queryset ───────────────────────────────────────────────

def get_report_queryset(
    *,
    from_date=None,
    to_date=None,
    doctor_id=None,
    rep_id=None,
    medicine_id=None,
):
    """
    Return an annotated SalesEntry queryset.

    Annotation added
    ────────────────
    line_value  – quantity × medicine.ptr  (computed at DB level)

    All FK look-ups use select_related to avoid N+1.
    """
    qs = (
        SalesEntry.objects
        .select_related("doctor", "medicine", "rep")
        .annotate(
            line_value=F("quantity") * F("medicine__ptr"),
        )
        .order_by("-entry_date", "-created_at")
    )

    # ── Apply filters ────────────────────────────────
    if from_date:
        qs = qs.filter(entry_date__gte=from_date)
    if to_date:
        qs = qs.filter(entry_date__lte=to_date)
    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)
    if rep_id:
        qs = qs.filter(rep_id=rep_id)
    if medicine_id:
        qs = qs.filter(medicine_id=medicine_id)

    return qs


# ─── Doctor-level ROI report ─────────────────────────────────────

def get_doctor_roi_report(
    *,
    from_date=None,
    to_date=None,
    doctor_id=None,
    rep_id=None,
    medicine_id=None,
):
    """
    Return a list of template-ready dicts with one row per
    SalesEntry, enriched with doctor-level ROI data.

    Columns per row
    ───────────────
    sl_no, doctor_name, location, doctor_type, medicine_name,
    rep_name, quantity, value, total_investment, entry_date,
    balance_roi, status

    Aggregation approach
    ────────────────────
    Investment totals and ROI targets are computed via Subquery on
    the Doctor model to avoid cross-join multiplication that would
    happen with a naive Sum across joined SalesEntry + Investment.
    """
    # ── Step 1: build the base SalesEntry queryset ──────────
    qs = (
        SalesEntry.objects
        .select_related("doctor", "medicine", "rep")
        .order_by("doctor__name", "-entry_date")
    )

    if from_date:
        qs = qs.filter(entry_date__gte=from_date)
    if to_date:
        qs = qs.filter(entry_date__lte=to_date)
    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)
    if rep_id:
        qs = qs.filter(rep_id=rep_id)
    if medicine_id:
        qs = qs.filter(medicine_id=medicine_id)

    # ── Step 2: pre-compute per-doctor investment & achieved ROI
    #    using separate aggregation queries to avoid duplication ──
    doctor_ids = list(qs.values_list("doctor_id", flat=True).distinct())

    # Investment totals per doctor (from Investment table)
    inv_rows = (
        Investment.objects
        .filter(doctor_id__in=doctor_ids)
        .values("doctor_id")
        .annotate(
            total_inv=Coalesce(
                Sum("amount"),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            total_roi_target=Coalesce(
                Sum(F("amount") * F("roi_ratio")),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
        )
        .values_list("doctor_id", "total_inv", "total_roi_target")
        .order_by()
    )
    inv_map = {
        did: {"investment": inv, "roi_target": roi}
        for did, inv, roi in inv_rows
    }

    # Achieved ROI per doctor (from SalesEntry, same date filters)
    achieved_qs = (
        SalesEntry.objects
        .filter(doctor_id__in=doctor_ids)
    )
    if from_date:
        achieved_qs = achieved_qs.filter(entry_date__gte=from_date)
    if to_date:
        achieved_qs = achieved_qs.filter(entry_date__lte=to_date)

    achieved_totals = {
        did: val
        for did, val in achieved_qs
        .values("doctor_id")
        .annotate(
            achieved=Coalesce(
                Sum(F("quantity") * F("medicine__ptr")),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
        )
        .values_list("doctor_id", "achieved")
        .order_by()
    }

    # ── Step 3: build flat rows ─────────────────────────────
    rows = []
    for idx, entry in enumerate(qs.iterator(chunk_size=500), start=1):
        did = entry.doctor_id
        doc_inv = inv_map.get(did, {"investment": Decimal("0"), "roi_target": Decimal("0")})
        investment = doc_inv["investment"]
        roi_target = doc_inv["roi_target"]
        achieved = achieved_totals.get(did, Decimal("0"))
        balance = roi_target - achieved

        # Status logic
        if roi_target == 0:
            status = "Pending"
        elif achieved >= roi_target:
            status = "Completed"
        else:
            status = "In Progress"

        rows.append({
            "sl_no": idx,
            "doctor_name": entry.doctor.name,
            "location": entry.doctor.location or "—",
            "doctor_type": entry.doctor.get_doctor_type_display(),
            "medicine_name": str(entry.medicine),
            "rep_name": entry.rep.get_full_name() or entry.rep.username,
            "quantity": entry.quantity,
            "value": entry.quantity * entry.medicine.ptr,
            "total_investment": investment,
            "entry_date": entry.entry_date,
            "balance_roi": balance,
            "status": status,
        })

    return rows


# ─── Aggregated summary ─────────────────────────────────────────

def get_report_summary(queryset):
    """
    Aggregate totals across the filtered SalesEntry queryset.

    Also computes total_investment and balance_roi from the set of
    doctors present in the filtered entries.
    """
    # --- Sales totals (from the queryset itself) ---
    agg = queryset.aggregate(
        total_quantity=Coalesce(
            Sum("quantity"), Value(0),
        ),
        total_value=Coalesce(
            Sum(F("quantity") * F("medicine__ptr")),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
    )

    # --- Investment totals for the doctors in the result set ---
    doctor_ids = queryset.values_list("doctor_id", flat=True).distinct()

    inv_agg = (
        Doctor.objects
        .filter(id__in=doctor_ids)
        .aggregate(
            total_investment=Coalesce(
                Sum("investments__amount"),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            total_roi_amount=Coalesce(
                Sum(
                    F("investments__amount") * F("investments__roi_ratio"),
                ),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
        )
    )

    achieved = agg["total_value"]
    investment = inv_agg["total_investment"]
    roi_amount = inv_agg["total_roi_amount"]
    balance = roi_amount - achieved

    return {
        "total_entries": queryset.count(),
        "total_quantity": agg["total_quantity"],
        "total_value": achieved,
        "total_investment": investment,
        "total_roi_amount": roi_amount,
        "balance_roi": balance,
    }


# ─── Excel export ────────────────────────────────────────────────

_HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
_HEADER_FILL = PatternFill(start_color="4361EE", end_color="4361EE", fill_type="solid")
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_SUMMARY_FILL = PatternFill(start_color="E8EDFF", end_color="E8EDFF", fill_type="solid")
_SUMMARY_FONT = Font(name="Calibri", bold=True, size=11)

_COLUMNS = [
    ("Sl No", 8),
    ("Doctor", 24),
    ("Area", 18),
    ("Type", 12),
    ("Medicine", 24),
    ("Sales Rep", 20),
    ("Quantity", 10),
    ("Value (₹)", 16),
    ("Investment (₹)", 16),
    ("Date", 14),
    ("Balance (₹)", 16),
    ("Status", 14),
]

_NUM_COLS = len(_COLUMNS)


def export_to_excel(roi_rows, summary):
    """
    Generate a styled .xlsx workbook from the doctor ROI rows and
    return a BytesIO buffer ready for HttpResponse streaming.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Doctor ROI Report"

    # ── Title row ────────────────────────────────────
    ws.merge_cells(f"A1:{get_column_letter(_NUM_COLS)}1")
    title_cell = ws["A1"]
    title_cell.value = "Medburg CRM — Doctor ROI Report"
    title_cell.font = Font(name="Calibri", bold=True, size=14, color="4361EE")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    # ── Header row ───────────────────────────────────
    header_row = 3
    for col_idx, (label, width) in enumerate(_COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=label)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGN
        cell.border = _THIN_BORDER
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[header_row].height = 24

    # ── Data rows ────────────────────────────────────
    data_align = Alignment(vertical="center")
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    currency_fmt = '#,##0.00'

    row_num = header_row + 1
    for row in roi_rows:
        ws.cell(row=row_num, column=1, value=row["sl_no"]).alignment = center_align
        ws.cell(row=row_num, column=2, value=row["doctor_name"]).alignment = data_align
        ws.cell(row=row_num, column=3, value=row["location"]).alignment = data_align
        ws.cell(row=row_num, column=4, value=row["doctor_type"]).alignment = data_align
        ws.cell(row=row_num, column=5, value=row["medicine_name"]).alignment = data_align
        ws.cell(row=row_num, column=6, value=row["rep_name"]).alignment = data_align
        ws.cell(row=row_num, column=7, value=row["quantity"]).alignment = center_align

        val_cell = ws.cell(row=row_num, column=8, value=float(row["value"]))
        val_cell.number_format = currency_fmt
        val_cell.alignment = right_align

        inv_cell = ws.cell(row=row_num, column=9, value=float(row["total_investment"]))
        inv_cell.number_format = currency_fmt
        inv_cell.alignment = right_align

        ws.cell(row=row_num, column=10, value=row["entry_date"]).alignment = data_align

        bal_cell = ws.cell(row=row_num, column=11, value=float(row["balance_roi"]))
        bal_cell.number_format = currency_fmt
        bal_cell.alignment = right_align

        ws.cell(row=row_num, column=12, value=row["status"]).alignment = center_align

        # Alternate row shading
        if row_num % 2 == 0:
            shade = PatternFill(start_color="F8F9FF", end_color="F8F9FF", fill_type="solid")
            for c in range(1, _NUM_COLS + 1):
                ws.cell(row=row_num, column=c).fill = shade

        for c in range(1, _NUM_COLS + 1):
            ws.cell(row=row_num, column=c).border = _THIN_BORDER

        row_num += 1

    # ── Summary block ────────────────────────────────
    summary_start = row_num + 2
    summary_items = [
        ("Total Entries", summary["total_entries"], False),
        ("Total Quantity", summary["total_quantity"], False),
        ("Total Sales Value (₹)", summary["total_value"], True),
        ("Total Investment (₹)", summary["total_investment"], True),
        ("Total ROI Target (₹)", summary["total_roi_amount"], True),
        ("Balance ROI (₹)", summary["balance_roi"], True),
    ]

    ws.merge_cells(f"A{summary_start}:B{summary_start}")
    heading = ws.cell(row=summary_start, column=1, value="Summary")
    heading.font = Font(name="Calibri", bold=True, size=12, color="4361EE")
    summary_start += 1

    for label, val, is_currency in summary_items:
        label_cell = ws.cell(row=summary_start, column=1, value=label)
        label_cell.font = _SUMMARY_FONT
        label_cell.fill = _SUMMARY_FILL
        label_cell.border = _THIN_BORDER

        val_cell = ws.cell(row=summary_start, column=2, value=float(val) if val else 0)
        val_cell.font = _SUMMARY_FONT
        val_cell.fill = _SUMMARY_FILL
        val_cell.border = _THIN_BORDER
        if is_currency:
            val_cell.number_format = currency_fmt
        val_cell.alignment = Alignment(horizontal="right")

        summary_start += 1

    # ── Freeze header ────────────────────────────────
    ws.freeze_panes = "A4"

    # ── Write to buffer ──────────────────────────────
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

