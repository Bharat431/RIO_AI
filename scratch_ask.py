import requests
url = "https://rio-ai.onrender.com/ask"
try:
    res = requests.post(url, json={"question": "hello"})
    print("Status:", res.status_code)
    print("Headers:", res.headers)
    print("Response text:", res.text)
except Exception as e:
    print(f"Error: {e}")
