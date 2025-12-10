import os
from typing import Optional

from gtts import gTTS
from googletrans import Translator


_translator = Translator()


def translate_text(text: str, src: str = 'auto', dest: str = 'en') -> str:
    text = (text or '').strip()
    if not text:
        return ''
    result = _translator.translate(text, src=src, dest=dest)
    return result.text


def synthesize_speech(text: str, lang: str = 'en') -> bytes:
    text = (text or '').strip()
    if not text:
        text = 'Hello'
    tts = gTTS(text=text, lang=lang)
    # Save to memory
    from io import BytesIO
    buf = BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


