import argparse

from jarvis.brain import Brain


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", action="store_true", help="type instead of speaking (no mic)")
    parser.add_argument("--silent", action="store_true", help="don't speak replies")
    args = parser.parse_args()

    brain = Brain()

    if args.text:
        from jarvis.io.stt import TextListener

        listener = TextListener()
    else:
        from jarvis.io.stt import Listener

        listener = Listener()

    if args.silent:
        from jarvis.io.tts import PrintSpeaker

        speaker = PrintSpeaker()
    else:
        from jarvis.io.tts import Speaker

        speaker = Speaker()

    wake = None
    if not args.text:
        from jarvis.io.wake import WakeWord

        wake = WakeWord()

    speaker.say("Online and at your service.")
    while True:
        if wake:
            print("[idle] waiting for wake word...")
            wake.wait()
            print("[awake] listening...")
        heard = listener.listen()
        if not heard:
            continue
        print(f"Heard: {heard}")
        if heard.lower() in ("exit", "quit", "goodbye"):
            speaker.say("Goodbye.")
            break
        speaker.say(brain.ask(heard))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
