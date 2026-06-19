import requests
import wave
import struct

# Create a small valid WAV file
filename = 'test_audio.wav'
sample_rate = 16000
with wave.open(filename, 'wb') as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)
    # Write 1 second of silence
    for _ in range(sample_rate):
        wav_file.writeframes(struct.pack('<h', 0))

print("Created test_audio.wav")

url = "http://localhost:8000/ask-voice"
try:
    with open(filename, 'rb') as f:
        files = {'file': (filename, f, 'audio/wav')}
        res = requests.post(url, files=files)
        
    print("Status:", res.status_code)
    print("Headers:", res.headers)
    print("Response text:", res.text)
except Exception as e:
    print(f"Error: {e}")
