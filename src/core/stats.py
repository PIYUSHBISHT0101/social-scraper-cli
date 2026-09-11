"""Statistical analytics calculator for social media datasets."""
import re
from collections import Counter
from statistics import mean, median
from typing import List, Dict, Any


class DatasetStatistics:
    """Calculates dataset metrics, emoji frequencies, and keyword breakdowns."""

    def calculate_summary(self, comments: List[Dict], meta: Dict = None) -> Dict[str, Any]:
        """Compute top-level summary KPIs."""
        if not comments:
            return {"total_comments": 0}

        meta = meta or {}
        total = len(comments)
        emoji_counts = [c.get("emoji_count", 0) for c in comments]
        total_emojis = sum(emoji_counts)
        emoji_comments_count = sum(1 for c in comments if c.get("emoji_count", 0) > 0)
        emoji_only_count = sum(1 for c in comments if c.get("emoji_only", False))
        questions_count = sum(1 for c in comments if c.get("is_question", False))
        urls_count = sum(1 for c in comments if c.get("has_url", False))

        all_emojis = [em for c in comments for em in c.get("emoji_list", [])]
        unique_emojis_count = len(set(all_emojis))

        platforms = list(set(c.get("platform", "Unknown") for c in comments))
        sources = list(set(c.get("source_name", c.get("channel_name", c.get("subreddit", c.get("account", "Unknown")))) for c in comments))

        return {
            "total_final_comments": total,
            "total_comments_with_emojis": emoji_comments_count,
            "emoji_only_comments": emoji_only_count,
            "questions_count": questions_count,
            "comments_with_links": urls_count,
            "total_emoji_occurrences": total_emojis,
            "unique_emoji_sequences": unique_emojis_count,
            "avg_emojis_per_comment": round(mean(emoji_counts), 2) if emoji_counts else 0.0,
            "median_emojis_per_comment": round(median(emoji_counts), 1) if emoji_counts else 0.0,
            "platforms_covered": ", ".join(platforms),
            "sources_covered_count": len(sources),
            "collection_duration": meta.get("duration", "N/A"),
        }

    def calculate_emoji_frequency(self, comments: List[Dict]) -> List[Dict]:
        """Rank emojis by occurrence count and percentage."""
        all_emojis = [em for c in comments for em in c.get("emoji_list", [])]
        if not all_emojis:
            return []

        counts = Counter(all_emojis)
        total_occurrences = len(all_emojis)
        total_comments = len(comments)

        result = []
        for emoji_str, freq in counts.most_common():
            comment_with_this_emoji = sum(1 for c in comments if emoji_str in c.get("emoji_list", []))
            pct_comments = (comment_with_this_emoji / total_comments * 100) if total_comments else 0.0
            pct_occurrences = (freq / total_occurrences * 100) if total_occurrences else 0.0
            result.append({
                "emoji": emoji_str,
                "frequency": freq,
                "percentage_of_comments": f"{pct_comments:.2f}%",
                "percentage_of_all_occurrences": f"{pct_occurrences:.2f}%",
            })
        return result

    def calculate_keyword_frequency(self, comments: List[Dict], top_n: int = 30) -> List[Dict]:
        """Rank top words and hashtags."""
        words = []
        for c in comments:
            text = str(c.get("comment", "") or "").lower()
            tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text)
            words.extend(tokens)

        stop_words = {"the", "and", "this", "that", "with", "for", "you", "are", "was", "were", "have", "has", "been", "all", "what", "just", "like", "get", "got", "can", "but", "not"}
        filtered_words = [w for w in words if w not in stop_words]
        counts = Counter(filtered_words)

        return [{"keyword": word, "frequency": count} for word, count in counts.most_common(top_n)]

    def calculate_source_breakdown(self, comments: List[Dict]) -> List[Dict]:
        """Group stats by source/channel/subreddit."""
        sources = {}
        for c in comments:
            src = c.get("source_name", c.get("channel_name", c.get("subreddit", c.get("account", "Unknown"))))
            if src not in sources:
                sources[src] = {
                    "source": src,
                    "platform": c.get("platform", "Unknown"),
                    "total_comments": 0,
                    "emoji_comments": 0,
                    "questions": 0,
                    "total_emojis": 0,
                }
            sources[src]["total_comments"] += 1
            if c.get("emoji_count", 0) > 0:
                sources[src]["emoji_comments"] += 1
            if c.get("is_question", False):
                sources[src]["questions"] += 1
            sources[src]["total_emojis"] += c.get("emoji_count", 0)

        for s in sources.values():
            s["avg_emojis"] = round(s["total_emojis"] / s["total_comments"], 2) if s["total_comments"] else 0.0

        return list(sources.values())
