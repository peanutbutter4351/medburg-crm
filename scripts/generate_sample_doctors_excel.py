import os
import openpyxl

def generate_excel():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Doctors"

    # Define headers
    headers = [
        "Doctor Name",
        "Phone Number",
        "Email",
        "Specialization",
        "Hospital / Clinic",
        "Location / City",
        "Doctor Mode",
        "Doctor Type"
    ]
    ws.append(headers)

    # 15 rows total (10 valid or semi-valid, 5 intentionally problematic)
    rows = [
        # 1. Valid Prepaid Trade
        ["Dr. Rajesh Kumar", "+919876543210", "rajesh.kumar@example.com", "Cardiologist", "Apollo Hospital", "Delhi", "prepaid", "trade"],
        
        # 2. Valid Postpaid Hospital
        ["Dr. Priya Patel", "+919812345678", "priya.patel@example.com", "Pediatrician", "Kokilaben Hospital", "Mumbai", "postpaid", "hospital"],
        
        # 3. Valid Prepaid Trade (different city)
        ["Dr. Amit Sharma", "+919988776655", "amit.sharma@example.com", "Orthopedic", "Fortis Hospital", "Bengaluru", "prepaid", "trade"],
        
        # 4. Valid Prepaid Stocking
        ["Dr. Sunita Rao", "+919123456789", "sunita.rao@example.com", "Gynecologist", "Manipal Hospital", "Hyderabad", "prepaid", "stocking"],
        
        # 5. Valid Postpaid Trade
        ["Dr. Vikram Singh", "+919000000001", "vikram.singh@example.com", "Dermatologist", "Medanta", "Gurugram", "postpaid", "trade"],
        
        # 6. Valid with blank optional fields (phone, email, clinic)
        ["Dr. Anjali Desai", "", "", "Oncologist", "", "Pune", "prepaid", "trade"],
        
        # 7. Valid with whitespace-heavy values (should be normalized/trimmed)
        ["  Dr. Rohan Shah   ", " +919111222333 ", "  rohan.shah@example.com  ", "  General Physician  ", "KEM Hospital", "  Mumbai  ", "postpaid", "trade"],
        
        # 8. Valid with mixed casing in Mode & Type (should be normalized)
        ["Dr. Meera Nair", "+918888888888", "MEERA.NAIR@EXAMPLE.COM", "Neurologist", "Aster Medcity", "Kochi", "PrePaid", "TRADE"],
        
        # 9. Valid Prepaid Trade
        ["Dr. Sanjay Gupta", "+917777777777", "sanjay.gupta@example.com", "Cardiologist", "Max Hospital", "Delhi", "prepaid", "trade"],
        
        # 10. Valid Postpaid Trade
        ["Dr. Deepa Balan", "+917777777700", "deepa.balan@example.com", "Gastroenterologist", "MIMS", "Calicut", "postpaid", "trade"],
        
        # --- PROBLEMATIC ROWS (5 rows) ---
        
        # 11. PROBLEMATIC 1: Duplicate doctor row (Name: Dr. Rajesh Kumar, Location: Delhi) - Duplicate of Row 1
        ["Dr. Rajesh Kumar", "+919876543210", "rajesh.kumar@example.com", "Cardiologist", "Apollo Hospital", "Delhi", "prepaid", "trade"],
        
        # 12. PROBLEMATIC 2: Invalid doctor mode ("invalid_mode")
        ["Dr. Sandeep Verma", "+919333333333", "sandeep.verma@example.com", "Urologist", "Apollo Hospital", "Kolkata", "invalid_mode", "trade"],
        
        # 13. PROBLEMATIC 3: Invalid doctor type ("invalid_type")
        ["Dr. Kavita Reddy", "+919444444444", "kavita.reddy@example.com", "ENT Specialist", "Care Hospital", "Hyderabad", "postpaid", "invalid_type"],
        
        # 14. PROBLEMATIC 4: Missing required column "Doctor Name"
        ["", "+919555555555", "nameless@example.com", "Radiologist", "Hinduja Hospital", "Mumbai", "prepaid", "trade"],
        
        # 15. PROBLEMATIC 5: Malformed email format (does not contain @ - will test system robustness)
        ["Dr. Suresh Pillai", "+919666666666", "suresh.pillai_invalid-email", "Nephrologist", "Amrita Hospital", "Kochi", "prepaid", "trade"]
    ]

    for row in rows:
        ws.append(row)

    # Make output path absolute to the project root
    output_filename = "sample_doctors.xlsx"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    output_path = os.path.join(project_root, output_filename)

    wb.save(output_path)
    print(f"Successfully generated sample Excel file at: {output_path}")

if __name__ == "__main__":
    generate_excel()
