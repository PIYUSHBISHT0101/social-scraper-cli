"""Unit test suite for Social Scraper CLI and Core Engines."""
import pytest
import os
import openpyxl
from src.core.detector import TextAnalyzer
from src.core.filter_engine import FilterEngine, FilterConfig
from src.core.deduplicator import Deduplicator
from src.core.language import LanguageDetector
from src.core.stats import DatasetStatistics
from src.core.exporter import DatasetExporter
from src.scrapers.youtube import YouTubeScraper
from src.scrapers.reddit import RedditScraper
from src.scrapers.instagram import InstagramScraper


def test_text_analyzer_emojis_and_structure():
    analyzer = TextAnalyzer()
    res = analyzer.enrich_comment({"comment": "What a great video? 😂🔥 Check this out https://example.com #awesome"})
    
    assert res["emoji_count"] == 2
    assert res["emoji_unique_count"] == 2
    assert "😂" in res["emoji_list"]
    assert "🔥" in res["emoji_list"]
    assert res["emoji_only"] is False
    assert res["is_question"] is True
    assert res["has_url"] is True
    assert "#awesome" in res["hashtags"]


def test_text_analyzer_emoji_only():
    analyzer = TextAnalyzer()
    res = analyzer.enrich_comment({"comment": "  🙌 ❤️ 🔥  "})
    assert res["emoji_count"] == 3
    assert res["emoji_only"] is True
    assert res["is_question"] is False


def test_filter_engine_modes():
    c_with_em = {"comment": "Hello! 🔥", "emoji_count": 1, "emoji_only": False, "is_question": False}
    c_no_em = {"comment": "Plain text question?", "emoji_count": 0, "emoji_only": False, "is_question": True}
    c_em_only = {"comment": "😂", "emoji_count": 1, "emoji_only": True, "is_question": False}

    # WITH_EMOJI mode
    engine_with = FilterEngine(FilterConfig(emoji_mode="WITH_EMOJI"))
    assert engine_with.evaluate(c_with_em)[0] is True
    assert engine_with.evaluate(c_no_em)[0] is False

    # WITHOUT_EMOJI mode
    engine_without = FilterEngine(FilterConfig(emoji_mode="WITHOUT_EMOJI"))
    assert engine_without.evaluate(c_no_em)[0] is True
    assert engine_without.evaluate(c_with_em)[0] is False

    # EMOJI_ONLY mode
    engine_only = FilterEngine(FilterConfig(emoji_mode="EMOJI_ONLY"))
    assert engine_only.evaluate(c_em_only)[0] is True
    assert engine_only.evaluate(c_with_em)[0] is False

    # Questions only
    engine_q = FilterEngine(FilterConfig(only_questions=True))
    assert engine_q.evaluate(c_no_em)[0] is True
    assert engine_q.evaluate(c_with_em)[0] is False


def test_filter_engine_keywords():
    engine = FilterEngine(FilterConfig(
        keywords_include=["review"],
        keywords_exclude=["scam", "telegram"]
    ))

    good_comment = {"comment": "Here is my honest review! ❤️", "emoji_count": 1}
    bad_kw_comment = {"comment": "Just commenting here", "emoji_count": 0}
    spam_comment = {"comment": "Great review, join my telegram", "emoji_count": 0}

    assert engine.evaluate(good_comment)[0] is True
    assert engine.evaluate(bad_kw_comment)[0] is False
    assert engine.evaluate(spam_comment)[0] is False


def test_deduplication():
    dedup = Deduplicator(by_comment_id=True, by_exact_text=True)
    comments = [
        {"comment_id": "c1", "comment": "First comment 🔥"},
        {"comment_id": "c1", "comment": "Duplicate ID 🔥"},
        {"comment_id": "c2", "comment": "First comment 🔥"},  # Duplicate text
        {"comment_id": "c3", "comment": "Unique second comment ❤️"},
    ]
    kept, stats = dedup.deduplicate(comments)
    assert len(kept) == 2
    assert stats["id_duplicates"] == 1
    assert stats["text_duplicates"] == 1


def test_language_detection():
    detector = LanguageDetector()
    assert detector.detect("This is an English comment.") == "en"
    assert detector.detect("यह एक हिंदी टिप्पणी है") == "hi"
    assert detector.detect("bhai kya mast video banayi yaar") == "hi-Latn"


def test_statistics_and_export(tmp_path):
    exporter = DatasetExporter(output_dir=str(tmp_path))
    stats_calc = DatasetStatistics()

    sample_comments = [
        {
            "id": 1,
            "comment_id": "101",
            "platform": "YouTube",
            "source_name": "@Creator",
            "target_id": "vid1",
            "target_url": "https://youtube.com/watch?v=vid1",
            "comment": "Awesome tutorial! 🔥",
            "emoji_list": ["🔥"],
            "emoji_count": 1,
            "emoji_unique_count": 1,
            "emoji_only": False,
            "is_question": False,
            "char_count": 18,
            "word_count": 3,
            "like_count": 25,
            "author": "Alice",
            "language": "en",
            "created_at": "2026-09-11T12:00:00Z",
            "collected_at": "2026-09-11T12:05:00Z",
            "source_url": "https://youtube.com/watch?v=vid1&lc=101",
        }
    ]

    summary = stats_calc.calculate_summary(sample_comments)
    emojis = stats_calc.calculate_emoji_frequency(sample_comments)
    sources = stats_calc.calculate_source_breakdown(sample_comments)

    files = exporter.export_all(
        comments=sample_comments,
        summary_stats=summary,
        emoji_stats=emojis,
        source_stats=sources,
        formats=["xlsx", "csv", "jsonl"],
        base_filename="test_dataset",
    )

    assert os.path.exists(files["xlsx"])
    assert os.path.exists(files["csv"])
    assert os.path.exists(files["jsonl"])

    wb = openpyxl.load_workbook(files["xlsx"])
    assert "Comments" in wb.sheetnames
    assert "Summary" in wb.sheetnames
    assert "Emoji_Stats" in wb.sheetnames
    assert "Source_Breakdown" in wb.sheetnames


def test_scrapers_normalization():
    yt = YouTubeScraper()
    c_yt = yt.normalize_comment("yt_1", "YouTube", "@Test", "v1", "url", "Great!", like_count="1,500", reply_count="250")
    assert c_yt["platform"] == "YouTube"
    assert c_yt["comment"] == "Great!"
    assert c_yt["like_count"] == 1500
    assert c_yt["reply_count"] == 250

    rd = RedditScraper()
    c_rd = rd.normalize_comment("rd_1", "Reddit", "r/test", "p1", "url", "Nice!")
    assert c_rd["platform"] == "Reddit"

    ig = InstagramScraper()
    c_ig = ig.normalize_comment("ig_1", "Instagram", "@test", "m1", "url", "Cool!")
    assert c_ig["platform"] == "Instagram"


def test_youtube_target_identification():
    yt = YouTubeScraper()
    # Video URLs
    assert yt.extract_video_id("https://www.youtube.com/watch?v=jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert yt.extract_video_id("https://youtu.be/jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert yt.extract_video_id("https://www.youtube.com/shorts/jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert yt.extract_video_id("jNQXAC9IVRw") == "jNQXAC9IVRw"
    # Channel URLs and handles should NOT be extracted as video IDs
    assert yt.extract_video_id("https://www.youtube.com/@CarryMinati") is None
    assert yt.extract_video_id("https://www.youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw") is None
    assert yt.extract_video_id("@CarryMinati") is None


def test_filter_engine_type_resilience():
    # None emoji_count should not raise TypeError
    engine = FilterEngine(FilterConfig(emoji_mode="WITH_EMOJI"))
    assert engine.evaluate({"comment": "test", "emoji_count": None}) == (False, "no_emoji")

    # None emoji_list in SPECIFIC_EMOJIS mode
    engine_sp = FilterEngine(FilterConfig(emoji_mode="SPECIFIC_EMOJIS", specific_emojis=["🔥"]))
    assert engine_sp.evaluate({"comment": "test", "emoji_list": None}) == (False, "missing_specific_emoji")

    # String likes with commas
    engine_likes = FilterEngine(FilterConfig(min_likes=100))
    assert engine_likes.evaluate({"comment": "test", "like_count": "50"}) == (False, "insufficient_likes")
    assert engine_likes.evaluate({"comment": "test", "like_count": "1,200"}) == (True, "passed")

    # None char/word counts fallback to text
    engine_len = FilterEngine(FilterConfig(min_chars=10))
    assert engine_len.evaluate({"comment": "short", "char_count": None}) == (False, "too_short_chars")
    assert engine_len.evaluate({"comment": "this is long enough", "char_count": None}) == (True, "passed")


def test_statistics_type_resilience():
    stats_calc = DatasetStatistics()
    comments = [
        {"comment": "one", "emoji_count": None, "emoji_list": None, "is_question": None, "has_url": None},
        {"comment": "two 🔥", "emoji_count": 1, "emoji_list": ["🔥"], "is_question": True, "has_url": False, "platform": "YouTube", "source_name": "@Creator"}
    ]
    summary = stats_calc.calculate_summary(comments)
    assert summary["total_final_comments"] == 2
    assert summary["total_comments_with_emojis"] == 1

    freq = stats_calc.calculate_emoji_frequency(comments)
    assert len(freq) == 1
    assert freq[0]["emoji"] == "🔥"

    breakdown = stats_calc.calculate_source_breakdown(comments)
    assert len(breakdown) == 2

