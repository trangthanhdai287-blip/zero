import sounddevice as sd
import numpy as np
import speech_recognition as sr
import io
import wave

SAMPLE_RATE = 16000
DURATION = 4  # Thời gian ghi âm mỗi chu kỳ

def wait_for_wake_word(wake_word="zero"):
    """Chờ đến khi nghe thấy từ khóa đánh thức 'zero' hoặc các từ bị nghe nhầm."""
    # Danh sách các biến thể phát âm tiếng Việt hay bị nhận diện nhầm
    aliases = [wake_word.lower()]
    if wake_word.lower() == "zero":
        aliases.extend(["siro", "xê rô", "di rô", "xê ro", "di ro"])
        
    print(f"🎙️ Zero đang ngủ... (Hãy gọi '{wake_word.capitalize()}' để đánh thức)")
    r = sr.Recognizer()
    
    while True:
        try:
            audio_data = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
            sd.wait()
            
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data.tobytes())
            wav_io.seek(0)
            
            with sr.AudioFile(wav_io) as source:
                audio = r.record(source)
                
            text = r.recognize_google(audio, language="vi-VN").lower()
            print(f"👂 Nghe được: {text}")
            
            # Kiểm tra xem có từ khóa chính hoặc bất kỳ biến thể nào không
            if any(alias in text for alias in aliases):
                print(f"🤖 Zero đã thức dậy!")
                return True
        except Exception:
            continue

def listen_active_command(duration=5):
    """Lắng nghe câu lệnh trực tiếp sau khi đã thức dậy (không cần gọi lại tên)."""
    print("🎙️ Zero đang lắng nghe lệnh của bạn...")
    r = sr.Recognizer()
    
    try:
        audio_data = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
        sd.wait()
        
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        wav_io.seek(0)
        
        with sr.AudioFile(wav_io) as source:
            audio = r.record(source)
            
        text = r.recognize_google(audio, language="vi-VN")
        print(f"🎯 Bạn nói: {text}")
        return text
    except Exception:
        return None