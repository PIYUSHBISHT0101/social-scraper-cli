"""Unicode-aware emoji detector and text structure analyzer."""
import re
import emoji

# Pre-compiled URL and hashtag regexes
URL_REGEX = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HASHTAG_REGEX = re.compile(r"#\w+", re.UNICODE)


class TextAnalyzer:
    """Detects Unicode emojis, text metrics, questions, and hashtags."""

    def __init__(self):
        self.library_name = "emoji"
        self.library_version = getattr(emoji, "__version__", "2.15.0")
        self.data_version = getattr(emoji, "EMOJI_DATA_VERSION", "See emoji library docs")

    def detect_emojis(self, text: str) -> dict:
        """Extract all emojis, counts, and flags from text."""
        if not text or not isinstance(text, str):
            return {
                "emoji_list": [],
                "emoji_count": 0,
                "emoji_unique_count": 0,
                "emoji_only": False,
            }

        extracted = emoji.emoji_list(text)
        emoji_list = [item["emoji"] for item in extracted]
        emoji_count = len(emoji_list)
        emoji_unique_count = len(set(emoji_list))

        # Check if emoji only
        text_without_emoji = emoji.replace_emoji(text, replace="").strip()
        emoji_only = bool(emoji_count > 0 and len(text_without_emoji) == 0)

        return {
            "emoji_list": emoji_list,
            "emoji_count": emoji_count,
            "emoji_unique_count": emoji_unique_count,
            "emoji_only": emoji_only,
        }

    def analyze_structure(self, text: str) -> dict:
        """Extract structural text features."""
        if not text or not isinstance(text, str):
            return {
                "char_count": 0,
                "word_count": 0,
                "is_question": False,
                "has_url": False,
                "hashtags": [],
            }

        stripped = text.strip()
        words = stripped.split()
        has_url = bool(URL_REGEX.search(text))
        # Strip URLs before question check so URL query parameters don't trigger false positives
        text_no_urls = URL_REGEX.sub("", text)
        is_question = "?" in text_no_urls or "¿" in text_no_urls
        hashtags = HASHTAG_REGEX.findall(text)

        return {
            "char_count": len(stripped),
            "word_count": len(words),
            "is_question": is_question,
            "has_url": has_url,
            "hashtags": hashtags,
        }

    def enrich_comment(self, comment_dict: dict) -> dict:
        """Enrich a comment dict with all detected emoji and text properties."""
        enriched = dict(comment_dict)
        text = enriched.get("comment", "") or ""

        emoji_info = self.detect_emojis(text)
        struct_info = self.analyze_structure(text)

        enriched.update(emoji_info)
        enriched.update(struct_info)
        return enriched
