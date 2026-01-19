import requests, os, base64
from time import sleep
import json
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================

API_URL    = "https://tngis.tn.gov.in/apps/gi_viewer_api/api/encumbrance_certificate"
REFERER    = "https://tngis.tn.gov.in/apps/gi_viewer/"
ORIGIN     = "https://tngis.tn.gov.in"

# 👉 Unga browser DevTools → Network la irundhu cookie-e copy paste pannunga
COOKIE = "_ga=GA1.1.882521766.1754558211; _ga_W44WTTGM0B=GS2.1.s1754558210$o1$g1$t1754558624$j45$l0$h0; PHPSESSID=0g6l6lr2vfj9khkcqir687vb0j"

# 👉 Default values (User to update for Govindacheri, Walaja, Ranipet)
# Note: TNGIS codes often differ from Census codes (Govindacheri Census: 630504).
# Common TNGIS District Codes: Vellore (Old) = 04, Ranipet (New) = 37 (Confirmed from error log)
DEFAULT_DISTRICT_CODE = "37" # Ranipet
DEFAULT_TALUK_CODE = "01"    # Trying 01 for Walaja (02 was Arcot)

OUTPUT_DIR = "Govindacheri_EC_Output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def looks_like_pdf_bytes(b: bytes) -> bool:
    return len(b) >= 4 and b[:4] == b"%PDF"

def save_pdf_bytes(data: bytes, name: str):
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    print("✅ Saved:", path)
    return path

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
        print(f"🔄 Requesting EC for: Village {payload['revVillageCode']}, Survey {payload['survey_number']}, Sub-div {payload['sub_division_number']}...")
        resp = s.post(API_URL, json=payload, headers=HEADERS, timeout=45)
        ct = resp.headers.get("Content-Type", "").lower()

        # 1) Direct PDF binary
        if "application/pdf" in ct or looks_like_pdf_bytes(resp.content):
            save_pdf_bytes(resp.content, filename)
            return True

        # 2) JSON response
        try:
            j = resp.json()
            
            # Request: Write response to JSON file
            debug_json_path = os.path.join(OUTPUT_DIR, "debug_last_response.json")
            with open(debug_json_path, "w", encoding="utf-8") as f:
                json.dump(j, f, indent=2)
            print(f"📄 Saved full API response to: {debug_json_path}")

        except Exception:
            print("❌ Not JSON / Not PDF. Status:", resp.status_code, "Snippet:", resp.text[:400])
            return False

        # Debug: Check for specific TNGIS status codes
        ec_data = j.get("EC", {})
        ec_status = ec_data.get("statusCode")
        
        if ec_status:
            if ec_status == 100:
                print("✅ Status 100: Success! Looking for PDF content...")
            elif ec_status == 1003:
                print("⚠️ Status 1003: No Data Found / Generation Failed for these details.")
            else:
                print(f"⚠️ API returned generic Status Code: {ec_status}")
        
        # Debug: Print Village Name if available to confirm location
        try:
            village_list = j.get("first", {}).get("data", {}).get("regVillageBeanList", [])
            if village_list:
                v = village_list[0]
                print(f"📍 Hit Village: {v.get('regVillageNameEng')} ({v.get('regVillageNameTam')}) | SRO: {v.get('sroNameEng')}")
        except:
            pass

        # quick debug
        if "message" in j:
            print("Server message:", j.get("message"))

        # 2a) Explicit check for EC -> Base64String
        b64 = None
        if "EC" in j and "Base64String" in j["EC"]:
            b64 = j["EC"]["Base64String"]
            print("Tv Found 'Base64String' inside 'EC' object.")

        # 2b) Fallback recursive scan
        if not b64:
            def find_b64(o):
                if isinstance(o, dict):
                    if "Base64String" in o:
                        return o["Base64String"]
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

        # 2c) Maybe JSON gives a PDF URL
        for k in ("url", "pdfUrl", "fileUrl"):
            url = j.get(k)
            if isinstance(url, str) and url.lower().endswith(".pdf"):
                r2 = s.get(url, headers={"Referer": REFERER, "User-Agent": HEADERS["User-Agent"]}, timeout=45)
                if r2.ok and looks_like_pdf_bytes(r2.content):
                    save_pdf_bytes(r2.content, filename)
                    return True

        print("⚠️ JSON received but no PDF found. Check 'debug_last_response.json' for details.")
        return False
        
    except Exception as e:
        print(f"❌ Download failed for {filename}: {e}")
        return False

# ==========================================
# MANUAL INPUT LOOP
# ==========================================

def get_user_input(prompt, default=None):
    """Helper to get input with optional default"""
    if default:
        user_val = input(f"{prompt} [{default}]: ").strip()
        return user_val if user_val else default
    else:
        while True:
            user_val = input(f"{prompt}: ").strip()
            if user_val:
                return user_val
            print("❌ Input cannot be empty.")

def manual_entry_mode():
    """Loop for manual input of EC details"""
    print("\n" + "="*50)
    print("   MANUAL EC DOWNLOADER")
    print("="*50)
    print("Target: Govindacheri, Walaja, Ranipet")
    print("Please find the TNGIS Codes from the website/DevTools if unknown.")
    print("="*50 + "\n")

    while True:
        try:
            print("\nEnter details for new EC (or Press Ctrl+C to quit):")
            
            district_code = get_user_input("District Code (e.g. 04 or 36 for Ranipet)")
            taluk_code = get_user_input("Taluk Code (e.g. 01 for Walaja?)")

            village_no = get_user_input("Village No (e.g. 084 for Govindacheri?)")
            survey_no = get_user_input("Survey No")
            sub_division = get_user_input("Sub Division (enter '-' for dash)", default="-")

            # Pad village number to 3 digits if needed
            village_no = village_no.zfill(3)

            # Construct payload
            payload = {
                "revDistrictCode": district_code,
                "revTalukCode": taluk_code,
                "revVillageCode": village_no,
                "survey_number": survey_no,
                "sub_division_number": sub_division
            }

            filename = f"{district_code}_{taluk_code}_{village_no}_{survey_no}_{sub_division}_EC.pdf"
            
            # Execute download
            success = try_download(payload, filename)
            
            if success:
                print("🎉 Success!")
            else:
                print("❌ Failed.")

            # Ask to continue
            cont = input("\nDownload another? (y/n) [y]: ").strip().lower()
            if cont == 'n':
                break
                
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    print(f"Output Directory: {os.path.abspath(OUTPUT_DIR)}")
    manual_entry_mode()
