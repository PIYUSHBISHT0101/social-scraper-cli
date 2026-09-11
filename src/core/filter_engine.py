"""Configurable multi-dimensional comment filter engine."""
import logging
from typing import Optional, List, Set

logger = logging.getLogger(__name__)

DEFAULT_BOT_INDICATORS = [
    "dm to promote",
    "follow me",
    "free crypto",
    "earn money",
    "check my page",
    "telegram",
    "whatsapp",
    "invest in",
    "binary trading",
    "click link in bio",
]


class FilterConfig:
    """Configuration data structure for comment filtering."""

    def __init__(
        self,
        emoji_mode: str = "ALL",  # ALL, WITH_EMOJI, WITHOUT_EMOJI, EMOJI_ONLY, SPECIFIC_EMOJIS
        specific_emojis: Optional[List[str]] = None,
        keywords_include: Optional[List[str]] = None,
        keywords_match_all: bool = False,  # True = AND, False = OR
        keywords_exclude: Optional[List[str]] = None,
        only_questions: bool = False,
        allow_urls: bool = True,
        min_chars: int = 0,
        max_chars: int = 10000,
        min_words: int = 0,
        max_words: int = 2000,
        min_likes: int = 0,
        remove_bots: bool = True,
        bot_indicators: Optional[List[str]] = None,
        language_filter: Optional[str] = None,  # None for all, or 'en', 'hi', etc.
    ):
        self.emoji_mode = emoji_mode.upper()
        self.specific_emojis = set(specific_emojis or [])
        self.keywords_include = [k.lower().strip() for k in (keywords_include or []) if k.strip()]
        self.keywords_match_all = keywords_match_all
        self.keywords_exclude = [k.lower().strip() for k in (keywords_exclude or []) if k.strip()]
        self.only_questions = only_questions
        self.allow_urls = allow_urls
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.min_words = min_words
        self.max_words = max_words
        self.min_likes = min_likes
        self.remove_bots = remove_bots
        self.bot_indicators = bot_indicators or DEFAULT_BOT_INDICATORS
        self.language_filter = language_filter.lower() if language_filter and language_filter != "ALL" else None


class FilterEngine:
    """Evaluates comments against dynamic user filter configurations."""

    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()

    def evaluate(self, comment: dict) -> tuple[bool, str]:
        """Test a single comment against all active filter rules.
        
        Returns:
            (passes: bool, reason: str)
        """
        cfg = self.config
        text = str(comment.get("comment", "") or "").strip()

        # 1. Empty check
        if not text:
            return False, "empty_text"

        # 2. Emoji filter
        emoji_count = comment.get("emoji_count", 0)
        emoji_only = comment.get("emoji_only", False)
        emoji_list = comment.get("emoji_list", [])

        if cfg.emoji_mode == "WITH_EMOJI" and emoji_count < 1:
            return False, "no_emoji"
        elif cfg.emoji_mode == "WITHOUT_EMOJI" and emoji_count > 0:
            return False, "has_emoji"
        elif cfg.emoji_mode == "EMOJI_ONLY" and not emoji_only:
            return False, "not_emoji_only"
        elif cfg.emoji_mode == "SPECIFIC_EMOJIS":
            found_specific = any(em in cfg.specific_emojis for em in emoji_list)
            if not found_specific:
                return False, "missing_specific_emoji"

        # 3. Question filter
        is_question = comment.get("is_question", False)
        if cfg.only_questions and not is_question:
            return False, "not_a_question"

        # 4. URL filter
        has_url = comment.get("has_url", False)
        if not cfg.allow_urls and has_url:
            return False, "contains_url"

        # 5. Length checks
        char_count = comment.get("char_count", len(text))
        if char_count < cfg.min_chars:
            return False, "too_short_chars"
        if char_count > cfg.max_chars:
            return False, "too_long_chars"

        word_count = comment.get("word_count", len(text.split()))
        if word_count < cfg.min_words:
            return False, "too_short_words"
        if word_count > cfg.max_words:
            return False, "too_long_words"

        # 6. Engagement / Likes threshold
        like_count = comment.get("like_count", comment.get("comment_score", 0)) or 0
        if isinstance(like_count, (int, float)) and like_count < cfg.min_likes:
            return False, "insufficient_likes"

        # 7. Keyword Inclusion
        text_lower = text.lower()
        if cfg.keywords_include:
            if cfg.keywords_match_all:
                matched_all = all(kw in text_lower for kw in cfg.keywords_include)
                if not matched_all:
                    return False, "missing_required_keyword"
            else:
                matched_any = any(kw in text_lower for kw in cfg.keywords_include)
                if not matched_any:
                    return False, "missing_included_keyword"

        # 8. Keyword Exclusion (Negative keywords)
        if cfg.keywords_exclude:
            has_excluded = any(kw in text_lower for kw in cfg.keywords_exclude)
            if has_excluded:
                return False, "contains_excluded_keyword"

        # 9. Bot & Spam indicators
        if cfg.remove_bots:
            author = str(comment.get("author", "") or "").lower()
            if author.endswith("bot") or author == "automoderator":
                return False, "bot_author"
            for indicator in cfg.bot_indicators:
                if indicator.lower() in text_lower:
                    return False, "bot_spam_pattern"

        # 10. Language filter
        if cfg.language_filter:
            lang = str(comment.get("language", "unknown")).lower()
            if lang != cfg.language_filter:
                return False, "language_mismatch"

        return True, "passed"

    def filter_batch(self, comments: list[dict]) -> tuple[list[dict], dict]:
        """Filter a list of comments and report statistics."""
        passed_comments = []
        stats = {
            "total_evaluated": len(comments),
            "passed": 0,
            "rejected": 0,
            "reasons": {},
        }

        for c in comments:
            passed, reason = self.evaluate(c)
            if passed:
                passed_comments.append(c)
                stats["passed"] += 1
            else:
                stats["rejected"] += 1
                stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1

        return passed_comments, stats
