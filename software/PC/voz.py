import queue
import time
import vosk
import sounddevice as sd
import json

model = vosk.Model("C:/Users/valen/OneDrive/Mis cosas/Facu/Cuat/GitHub/Almacenamiento-con-Grua-Torre-Coluccio-Gomez/software/PC/vosk-model-small-es-0.42")

def deteccion_por_voz(colavoz):
    recognizer = vosk.KaldiRecognizer(model, 16000)

    def callback(indata, frames, time_info, status):
        if recognizer.AcceptWaveform(bytes(indata)):
            result = json.loads(recognizer.Result())
            texto = result.get("text", "").strip()
            if texto:
                colavoz.put(f"voz {texto}")
                print(f"🎙️ Enviado voz: {texto}")

    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                           channels=1, callback=callback):
        print("🎤 Escuchando por voz (Ctrl+C para detener)...")
        while True:
            time.sleep(0.1)