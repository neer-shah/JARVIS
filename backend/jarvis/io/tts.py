class Speaker:
    """Text -> speech via offline Windows voices. Swap for any class with say(str)."""

    def say(self, text: str) -> None:
        import pyttsx3

        print(f"JARVIS: {text}")
        engine = pyttsx3.init()  # re-init each time; avoids pyttsx3 hanging on repeated runAndWait
        engine.say(text)
        engine.runAndWait()


class PrintSpeaker:
    def say(self, text: str) -> None:
        print(f"JARVIS: {text}")
