import speech_recognition as sr
from pydub import AudioSegment
import os
import tempfile

def process_audio(audio_path: str) -> str:
    """
    Converts audio to WAV (if necessary) and transcribes using Google Web Speech API.
    """
    wav_path = None
    try:
        # Convert to WAV using pydub
        audio = AudioSegment.from_file(audio_path)
        
        # Create temp file for wav
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        audio.export(wav_path, format="wav")
        
        # Initialize recognizer
        recognizer = sr.Recognizer()
        
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            
            # Perform transcription
            text = recognizer.recognize_google(audio_data)
            return text
            
    except sr.UnknownValueError:
        raise ValueError("Speech recognition could not understand audio")
    except sr.RequestError as e:
        raise ValueError(f"Could not request results from Speech Recognition service; {e}")
    except Exception as e:
        raise ValueError(f"Error processing audio: {e}")
    finally:
        # Cleanup temp file
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
