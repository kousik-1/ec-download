# api_debug.py
import requests
import json
import base64

def debug_api_response():
    """Debug script to understand API response structure"""
    
    # API endpoint
    url = "https://tngis.tn.gov.in/apps/gi_viewer_api/api/encumbrance_certificate"
    
    # Sample payload (modify with your actual data)
    payload = {
        "district_code": "29",
        "taluk_code": "08", 
        "village_code": "040",
        "survey_no": "384",
        "sub_div_no": "2A"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json',
        'Origin': 'https://tngis.tn.gov.in',
        'Referer': 'https://tngis.tn.gov.in/',
    }
    
    print("🔍 API Response Debug")
    print("=" * 50)
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse Keys: {list(data.keys())}")
            
            # Analyze each key
            for key, value in data.items():
                print(f"\n--- {key} ---")
                if isinstance(value, str):
                    print(f"Type: string, Length: {len(value)}")
                    # Check if it might be base64
                    if len(value) > 100 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in value):
                        print("🔍 This looks like base64 data!")
                        try:
                            decoded = base64.b64decode(value)
                            print(f"Decoded size: {len(decoded)} bytes")
                            if decoded.startswith(b'%PDF'):
                                print("✅ This is a valid PDF!")
                            else:
                                print("❌ Not a valid PDF")
                        except Exception as e:
                            print(f"❌ Base64 decode failed: {e}")
                    else:
                        print(f"Value preview: {value[:100]}...")
                elif isinstance(value, dict):
                    print(f"Type: dict, Keys: {list(value.keys())}")
                elif isinstance(value, list):
                    print(f"Type: list, Length: {len(value)}")
                else:
                    print(f"Type: {type(value).__name__}, Value: {value}")
                    
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    debug_api_response()