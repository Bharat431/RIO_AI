import requests
import sys
import json

base_url = "http://localhost:8001"
pdf_path = "test_interview.pdf"

print("--- Testing PDF Upload ---")
try:
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path, f, 'application/pdf')}
        res = requests.post(f"{base_url}/upload-pdf", files=files)
        print("Status:", res.status_code)
        data = res.json()
        print("Response:", json.dumps(data, indent=2))
        
        if "analysis" in data:
            print("SUCCESS: Analysis received from upload.")
        else:
            print("ERROR: No analysis in response.")
            sys.exit(1)
except Exception as e:
    print(f"Error during upload: {e}")
    sys.exit(1)

print("\n--- Testing Semantic Match (Q: 'tell me something about you') ---")
try:
    res = requests.post(f"{base_url}/ask", json={"question": "tell me something about you"})
    print("Status:", res.status_code)
    print("Response:", json.dumps(res.json(), indent=2))
except Exception as e:
    print(f"Error during ask: {e}")

print("\n--- Testing Out of Box Match (Q: 'how should I dress for a remote interview') ---")
try:
    res = requests.post(f"{base_url}/ask", json={"question": "how should I dress for a remote interview"})
    print("Status:", res.status_code)
    print("Response:", json.dumps(res.json(), indent=2))
except Exception as e:
    print(f"Error during ask: {e}")

