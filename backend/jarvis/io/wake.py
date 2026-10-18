import numpy as np
import pyaudio
from openwakeword.model import Model

RATE = 16000
CHUNK = 1280  # 80 ms, the frame size openwakeword expects


class WakeWord:
    """Blocks until the wake phrase is heard. Runs fully offline on-device: no audio is
    sent anywhere until this fires. Swap for any class with a wait() method."""

    def __init__(self, model: str = "hey_jarvis", threshold: float = 0.5):
        self.model_name = model
        self.threshold = threshold
        self.model = Model(wakeword_models=[model], inference_framework="onnx")
        self.pa = pyaudio.PyAudio()

    def wait(self, should_stop=lambda: False) -> bool:
        """Returns True when the wake phrase is heard, False if should_stop() turned true first."""
        # Open the mic only while waiting so it's free for the speech recogniser afterwards.
        stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
        self.model.reset()
        try:
            while not should_stop():
                frame = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
                scores = self.model.predict(frame)
                if any(v >= self.threshold for k, v in scores.items() if k.startswith(self.model_name)):
                    return True
            return False
        finally:
            stream.stop_stream()
            stream.close()
