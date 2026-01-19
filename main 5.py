# Working script to download Encumbrance Certificates in bulk from Excel input
import requests, os, base64
import pandas as pd
from time import sleep
import json
from datetime import datetime

API_URL    = "https://tngis.tn.gov.in/apps/gi_viewer_api/api/encumbrance_certificate"
REFERER    = "https://tngis.tn.gov.in/apps/gi_viewer/"
ORIGIN     = "https://tngis.tn.gov.in"

# 👉 Unga browser DevTools → Network la irundhu cookie-e copy paste pannunga
COOKIE = "_ga=GA1.1.882521766.1754558211; _ga_W44WTTGM0B=GS2.1.s1754558210$o1$g1$t1754558624$j45$l0$h0; PHPSESSID=0g6l6lr2vfj9khkcqir687vb0j"

# 👉 Default values for district and taluk (constant)
DEFAULT_DISTRICT_CODE = "29"
DEFAULT_TALUK_CODE = "08"

# 👉 Excel file path
EXCEL_FILE = r"N:\EC_Download\Missing_file_list\ec_files_382_moolakaraipatti.xlsx"   # Change this to your Excel file path

OUTPUT_DIR = "Moolakaraipatti_EC_Output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# File to store failed entries for retry
FAILED_ENTRIES_FILE = "failed_entries.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json",
    "Origin": ORIGIN,
    "Referer": REFERER,
    "X-Requested-With": "XMLHttpRequest",
    # 🔑 ivlo than main fix:
    "x-app-name": "demo",
    "Cookie": COOKIE,
}

def looks_like_pdf_bytes(b: bytes) -> bool:
    return len(b) >= 4 and b[:4] == b"%PDF"

def save_pdf_bytes(data: bytes, name: str):
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    print("✅ Saved:", path)
    return path

def save_failed_entries(failed_entries):
    """Save failed entries to a JSON file for retry"""
    with open(FAILED_ENTRIES_FILE, 'w') as f:
        json.dump(failed_entries, f, indent=2)
    print(f"💾 Saved {len(failed_entries)} failed entries to {FAILED_ENTRIES_FILE}")

def load_failed_entries():
    """Load failed entries from JSON file"""
    if os.path.exists(FAILED_ENTRIES_FILE):
        with open(FAILED_ENTRIES_FILE, 'r') as f:
            return json.load(f)
    return []

def clear_failed_entries():
    """Clear the failed entries file"""
    if os.path.exists(FAILED_ENTRIES_FILE):
        os.remove(FAILED_ENTRIES_FILE)
        print("🗑️ Cleared failed entries file")

def try_download(payload: dict, filename: str = None) -> bool:
    """Try to download EC and return True if successful, False otherwise"""
    s = requests.Session()
    
    # Generate filename if not provided
    if not filename:
        filename = f"{payload['revDistrictCode']}_{payload['revTalukCode']}_{payload['revVillageCode']}_{payload['survey_number']}_{payload['sub_division_number']}_EC.pdf"

    # Check if file already exists
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        print(f"📁 File already exists, skipping: {filename}")
        return True
        
    try:
        resp = s.post(API_URL, json=payload, headers=HEADERS, timeout=45)
        ct = resp.headers.get("Content-Type", "").lower()

        # 1) Direct PDF binary
        if "application/pdf" in ct or looks_like_pdf_bytes(resp.content):
            save_pdf_bytes(resp.content, filename)
            return True

        # 2) JSON response
        try:
            j = resp.json()
        except Exception:
            print("❌ Not JSON / Not PDF. Status:", resp.status_code, "Snippet:", resp.text[:400])
            return False

        # quick debug
        if "message" in j:
            print("Server message:", j.get("message"))

        # 2a) Base64 scan (nested keys handle)
        def find_b64(o):
            if isinstance(o, dict):
                for v in o.values():
                    r = find_b64(v)
                    if r: return r
            elif isinstance(o, list):
                for v in o:
                    r = find_b64(v)
                    if r: return r
            elif isinstance(o, str):
                s = o.strip()
                if s.startswith("data:application/pdf;base64,"):
                    s = s.split(",",1)[1]
                if (len(s) > 100) and (s[:5].lower() == "jvber"):
                    return s
            return None

        b64 = find_b64(j)
        if b64:
            try:
                pdf = base64.b64decode(b64)
                save_pdf_bytes(pdf, filename)
                return True
            except Exception as e:
                print("Base64 decode fail:", e)

        # 2b) Maybe JSON gives a PDF URL
        for k in ("url", "pdfUrl", "fileUrl"):
            url = j.get(k)
            if isinstance(url, str) and url.lower().endswith(".pdf"):
                r2 = s.get(url, headers={"Referer": REFERER, "User-Agent": HEADERS["User-Agent"]}, timeout=45)
                if r2.ok and looks_like_pdf_bytes(r2.content):
                    save_pdf_bytes(r2.content, filename)
                    return True

        print("⚠️ JSON received but no PDF/base64 found. Full JSON (trimmed):", str(j)[:800])
        return False
        
    except Exception as e:
        print(f"❌ Download failed for {filename}: {e}")
        return False

def retry_failed_entries(failed_entries):
    """Retry failed downloads with longer delay"""
    if not failed_entries:
        print("🎉 No failed entries to retry!")
        return
    
    print(f"\n🔄 Starting retry process for {len(failed_entries)} failed entries...")
    print("⏰ Using 10-second delay between retry requests for better stability")
    
    retry_success_count = 0
    still_failed_entries = []
    
    for i, entry in enumerate(failed_entries, 1):
        print(f"\n🔄 Retry {i}/{len(failed_entries)}: {entry['village_no']}-{entry['survey_no']}-{entry['sub_division']}")
        
        payload = {
            "revDistrictCode": DEFAULT_DISTRICT_CODE,
            "revTalukCode": DEFAULT_TALUK_CODE,
            "revVillageCode": entry['village_no'],
            "survey_number": entry['survey_no'],
            "sub_division_number": entry['sub_division']
        }
        
        filename = entry.get('filename', f"{DEFAULT_DISTRICT_CODE}_{DEFAULT_TALUK_CODE}_{entry['village_no']}_{entry['survey_no']}_{entry['sub_division']}_EC.pdf")
        
        if try_download(payload, filename):
            retry_success_count += 1
            print(f"✅ Retry successful!")
        else:
            still_failed_entries.append(entry)
            print(f"❌ Retry failed")
        
        # 10-second delay between retry requests
        if i < len(failed_entries):
            print("⏳ Waiting 10 seconds before next retry...")
            sleep(20)
    
    print(f"\n🔄 Retry process completed!")
    print(f"✅ Successfully recovered: {retry_success_count} files")
    print(f"❌ Still failed: {len(still_failed_entries)} files")
    
    # Update failed entries file with remaining failures
    if still_failed_entries:
        save_failed_entries(still_failed_entries)
        print(f"💾 Updated {FAILED_ENTRIES_FILE} with {len(still_failed_entries)} remaining failed entries")
    else:
        clear_failed_entries()
        print("🎉 All failed entries have been successfully recovered!")

def process_excel_data(excel_file):
    """Process Excel file and download ECs for all entries"""
    failed_entries = []
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_file)
        
        # Validate required columns
        required_columns = ['Village_No', 'Survey No.', 'Sub Division']
        for col in required_columns:
            if col not in df.columns:
                print(f"❌ Missing required column: {col}")
                return
        
        print(f"📊 Found {len(df)} records in Excel file")
        
        success_count = 0
        skip_count = 0
        
        for index, row in df.iterrows():
            village_no = str(row['Village_No']).zfill(3)  # Ensure 3-digit format
            survey_no = str(row['Survey No.'])
            sub_division = str(row['Sub Division'])
            
            print(f"\n📄 Processing: Village {village_no}, Survey {survey_no}, Sub-division '{sub_division}'")
            
            # Handle dash case - directly use "-" as sub_division_number
            if sub_division.strip() == "-":
                print(f"🔍 Dash detected! Using '-' directly as sub-division number...")
                
                payload = {
                    "revDistrictCode": DEFAULT_DISTRICT_CODE,
                    "revTalukCode": DEFAULT_TALUK_CODE,
                    "revVillageCode": village_no,
                    "survey_number": survey_no,
                    "sub_division_number": "-"  # Directly use dash
                }
                
                filename = f"{DEFAULT_DISTRICT_CODE}_{DEFAULT_TALUK_CODE}_{village_no}_{survey_no}_EC.pdf"
                
                if try_download(payload, filename):
                    success_count += 1
                else:
                    skip_count += 1
                    # Record failed entry
                    failed_entries.append({
                        'village_no': village_no,
                        'survey_no': survey_no,
                        'sub_division': "-",
                        'filename': filename,
                        'reason': 'Download failed for dash entry'
                    })
                
                # 6-second delay between main process requests
                if index < len(df) - 1:  # Don't wait after the last request
                    print("⏳ Waiting 6 seconds before next request...")
                    sleep(10)
                    
            else:
                # Normal case - single subdivision
                payload = {
                    "revDistrictCode": DEFAULT_DISTRICT_CODE,
                    "revTalukCode": DEFAULT_TALUK_CODE,
                    "revVillageCode": village_no,
                    "survey_number": survey_no,
                    "sub_division_number": sub_division
                }
                
                filename = f"{DEFAULT_DISTRICT_CODE}_{DEFAULT_TALUK_CODE}_{village_no}_{survey_no}_{sub_division}_EC.pdf"
                
                if try_download(payload, filename):
                    success_count += 1
                else:
                    skip_count += 1
                    # Record failed entry
                    failed_entries.append({
                        'village_no': village_no,
                        'survey_no': survey_no,
                        'sub_division': sub_division,
                        'filename': filename,
                        'reason': 'Download failed'
                    })
                
                # 6-second delay between main process requests
                if index < len(df) - 1:  # Don't wait after the last request
                    print("⏳ Waiting 6 seconds before next request...")
                    sleep(20)
        
        print(f"\n🎉 Main download process completed!")
        print(f"✅ Successfully downloaded: {success_count} files")
        print(f"❌ Failed/Skipped: {skip_count} files")
        print(f"📁 Files saved in: {os.path.abspath(OUTPUT_DIR)}")
        
        # Save failed entries for retry
        if failed_entries:
            save_failed_entries(failed_entries)
            print(f"\n⚠️ {len(failed_entries)} entries failed during initial download")
            print("🔄 Starting retry process after 10-second delay...")
            sleep(20)  # Wait before starting retry
            retry_failed_entries(failed_entries)
        else:
            print("🎉 All downloads completed successfully!")
            clear_failed_entries()
        
    except Exception as e:
        print(f"❌ Error processing Excel file: {e}")

if __name__ == "__main__":
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ Excel file '{EXCEL_FILE}' not found!")
        print("Please create an Excel file with columns: Village_No, Survey No., Sub Division")
    else:
        process_excel_data(EXCEL_FILE)

    print("\n👉 Tips:\n"
          "1) Cookie (PHPSESSID) expired-aa? Browser-la EC open panni fresh-a copy panni COOKIE varila paste pannunga.\n"
          "2) x-app-name value DevTools headers la vera maari irundhaa (demo illa), adha HEADERS-la update pannunga.\n"
          "3) DevTools la response JSON-la pdf URL/base64 key name enna-nu parunga; venumna script la key names add panlaam.\n")