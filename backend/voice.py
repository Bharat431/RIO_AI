import speech_recognition as sr
from pydub import AudioSegment
from pydub.utils import which
import os
import tempfile

def process_audio(audio_path: str) -> str:
    """
    Transcribes audio using Google Web Speech API.
    WAV files are handled natively. Other formats need ffmpeg (converted via pydub).
    """
    recognizer = sr.Recognizer()

    # Try native WAV support first (no ffmpeg needed)
    try:
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data)
    except sr.UnknownValueError:
        raise ValueError("Speech recognition could not understand audio. Please speak more clearly.")
    except sr.RequestError as e:
        raise ValueError(f"Could not request results from Speech Recognition service; {e}")
    except Exception:
        pass  # Fall through to ffmpeg path below

    # Non-WAV format — try pydub with ffmpeg
    if not which("ffmpeg"):
        raise ValueError(
            "ffmpeg not found. Install ffmpeg (https://ffmpeg.org). "
            "On Windows: choco install ffmpeg or download from ffmpeg.org. "
            "On macOS: brew install ffmpeg. On Linux: sudo apt install ffmpeg."
        )

    wav_path = None
    try:
        audio = AudioSegment.from_file(audio_path)
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        audio.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text

    except sr.UnknownValueError:
        raise ValueError("Speech recognition could not understand audio")
    except sr.RequestError as e:
        raise ValueError(f"Could not request results from Speech Recognition service; {e}")
    except Exception as e:
        raise ValueError(f"Error processing audio: {e}")
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
