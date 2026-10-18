import speech_recognition as sr


class Listener:
    """Microphone -> text. Swap this class (e.g. for Whisper) as long as listen() returns str|None."""

    def __init__(self):
        self.rec = sr.Recognizer()
        self.mic = sr.Microphone()
        with self.mic as source:
            self.rec.adjust_for_ambient_noise(source, duration=1)

    def listen(self) -> str | None:
        with self.mic as source:
            try:
                audio = self.rec.listen(source, timeout=10, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                return None
        try:
            return self.rec.recognize_google(audio)  # free web API, no key needed
        except (sr.UnknownValueError, sr.RequestError):
            return None


class TextListener:
    """Keyboard fallback for testing without a mic."""

    def listen(self) -> str | None:
        return input("You: ").strip() or None
