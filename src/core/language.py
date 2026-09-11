"""Language and script detection module."""
import re
import unicodedata

# Common script detection regexes
DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")
ARABIC_REGEX = re.compile(r"[\u0600-\u06FF]")
CJK_REGEX = re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]")
CYRILLIC_REGEX = re.compile(r"[\u0400-\u04FF]")

# Common English vocabulary indicators
ENGLISH_COMMON_WORDS = {
    "the", "is", "are", "was", "were", "have", "has", "been", "this", "that",
    "with", "for", "not", "you", "all", "can", "but", "what", "just", "like",
    "get", "got", "and", "good", "great", "very", "bro", "bruh", "lol", "lmao",
    "love", "best", "video", "game", "channel", "subscribe", "please", "thanks"
}

# Common Hinglish / Romanized Hindi indicators
HINGLISH_WORDS = {
    "bhai", "yaar", "kya", "nahi", "haan", "acha", "achha", "badiya", "sahi",
    "mera", "meri", "hum", "tum", "aap", "karo", "kardo", "dekho", "chal",
    "khatam", "paiso", "sabse", "wala", "wali", "wale", "kuch", "bahut"
}


class LanguageDetector:
    """Classifies script and language of social media text."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def detect(self, text: str) -> str:
        """Detect language code or script tag."""
        if not self.enabled or not text or not isinstance(text, str):
            return "unknown"

        text_clean = text.strip()
        if not text_clean:
            return "unknown"

        # 1. Script checks
        if DEVANAGARI_REGEX.search(text_clean):
            return "hi"  # Hindi (Devanagari script)
        if ARABIC_REGEX.search(text_clean):
            return "ar"  # Arabic
        if CJK_REGEX.search(text_clean):
            return "zh/ja/ko"
        if CYRILLIC_REGEX.search(text_clean):
            return "ru"

        # 2. Latin script word token matching
        tokens = set(re.findall(r"\b[a-zA-Z]+\b", text_clean.lower()))
        if not tokens:
            return "unknown"

        hinglish_matches = tokens.intersection(HINGLISH_WORDS)
        english_matches = tokens.intersection(ENGLISH_COMMON_WORDS)

        if len(hinglish_matches) > 0 and len(hinglish_matches) >= len(english_matches):
            return "hi-Latn"  # Hinglish / Romanized Hindi
        if len(english_matches) > 0:
            return "en"

        return "en"  # Default for Latin text
