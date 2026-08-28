import os
import sys
import asyncio
import tempfile
import threading
import time
import subprocess

# Vá lỗi WinError 50 cho speech_recognition
_orig_popen_init = subprocess.Popen.__init__
def _patched_popen_init(self, *args, **kwargs):
    if kwargs.get("stderr") is None:
        kwargs["stderr"] = subprocess.DEVNULL
    if kwargs.get("stdin") is None:
        kwargs["stdin"] = subprocess.DEVNULL
    _orig_popen_init(self, *args, **kwargs)
subprocess.Popen.__init__ = _patched_popen_init

import sounddevice as sd
import numpy as np
import speech_recognition as sr
import wave

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import pygame
except ImportError:
    pygame = None

TTS_VOICE = "vi-VN-HoaiMyNeural"   # Giọng nữ Việt Nam
TTS_RATE = "+0%"
TTS_VOLUME = 1.0
_TTS_LOCK = threading.Lock()

def _ensure_tts_dependencies():
    missing = []
    if edge_tts is None:
        missing.append("edge-tts")
    if pygame is None:
        missing.append("pygame")
    if missing:
        print("❌ Thiếu thư viện TTS: " + ", ".join(missing))
        print(f"   Cài bằng lệnh: {sys.executable} -m pip install {' '.join(missing)}")
        return False
    return True

async def _make_vietnamese_audio(text, filename):
    communicate = edge_tts.Communicate(text=text, voice=TTS_VOICE, rate=TTS_RATE)
    await communicate.save(filename)

def _play_mp3(filename):
    pygame.mixer.init()
    try:
        pygame.mixer.music.set_volume(TTS_VOLUME)
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(30)
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.quit()

def speak(text):
    print(f"AI: {text}")
    if not text or not str(text).strip():
        return
    if not _ensure_tts_dependencies():
        return

    with _TTS_LOCK:
        filename = None
        try:
            fd, filename = tempfile.mkstemp(prefix="assistant_tts_", suffix=".mp3")
            os.close(fd)
            asyncio.run(_make_vietnamese_audio(str(text), filename))
            _play_mp3(filename)
        except Exception as e:
            print(f"⚠️ Lỗi TTS tiếng Việt: {e}")
        finally:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except OSError:
                    pass

def record_audio(filename="command.wav", fs=16000, max_duration=8,
                  silence_duration=0.8, min_speech_duration=0.25):
    print("\n🎤 Đang lắng nghe lệnh từ bạn (hãy nói)...")
    chunk_duration = 0.03
    chunk_size = max(1, int(fs * chunk_duration))
    frames = []
    silence_chunks_needed = int(silence_duration / chunk_duration)
    min_speech_chunks = int(min_speech_duration / chunk_duration)

    state = {
        "speech_started": False,
        "silence_count": 0,
        "speech_count": 0,
        "noise_floor": None,
        "stop": False,
    }

    def callback(indata, frames_count, time_info, status):
        chunk = indata[:, 0].copy()
        frames.append(chunk)
        energy = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))

        if state["noise_floor"] is None:
            state["noise_floor"] = energy
            return

        if not state["speech_started"]:
            state["noise_floor"] = 0.95 * state["noise_floor"] + 0.05 * energy

        threshold = max(state["noise_floor"] * 3, 150)

        if energy > threshold:
            state["speech_started"] = True
            state["speech_count"] += 1
            state["silence_count"] = 0
        elif state["speech_started"]:
            state["silence_count"] += 1

        if (state["speech_started"]
                and state["speech_count"] >= min_speech_chunks
                and state["silence_count"] >= silence_chunks_needed):
            state["stop"] = True

    try:
        with sd.InputStream(samplerate=fs, channels=1, dtype='int16',
                             blocksize=chunk_size, callback=callback):
            start = time.time()
            while not state["stop"] and (time.time() - start) < max_duration:
                sd.sleep(30)
    except Exception as e:
        print(f"⚠️ Lỗi ghi âm, dùng chế độ ghi cố định dự phòng: {e}")
        audio = sd.rec(int(2 * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        frames = [audio[:, 0]]

    audio = np.concatenate(frames) if frames else np.zeros(chunk_size, dtype='int16')

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(audio.tobytes())
    return filename

def listen_command():
    filename = record_audio()
    r = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        audio_data = r.record(source)
    try:
        text = r.recognize_google(audio_data, language="vi-VN")
        print(f"Bạn nói: {text}")
        return text.lower()
    except sr.UnknownValueError:
        print("Không nghe rõ bạn nói gì...")
        return ""
    except sr.RequestError:
        speak("Lỗi kết nối mạng rồi bạn ơi.")
        return ""
    finally:
        if os.path.exists(filename):
            os.remove(filename)