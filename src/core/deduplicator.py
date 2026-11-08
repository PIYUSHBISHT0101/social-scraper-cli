"""Multi-mode deduplication module for social media datasets."""
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class Deduplicator:
    """Deduplicates comments by ID, exact text, and author frequency."""

    def __init__(
        self,
        by_comment_id: bool = True,
        by_exact_text: bool = True,
        max_comments_per_author: Optional[int] = None,
    ):
        self.by_comment_id = by_comment_id
        self.by_exact_text = by_exact_text
        self.max_comments_per_author = max_comments_per_author

    def deduplicate(self, comments: List[Dict]) -> Tuple[List[Dict], Dict]:
        """Apply deduplication rules."""
        seen_ids = set()
        seen_texts = set()
        author_counts = {}

        kept = []
        stats = {
            "initial_count": len(comments),
            "id_duplicates": 0,
            "text_duplicates": 0,
            "author_limit_exceeded": 0,
            "total_removed": 0,
            "total_kept": 0,
        }

        for c in comments:
            cid = str(c.get("comment_id", "") or "").strip()
            text = str(c.get("comment", "") or "").strip()
            author = str(c.get("author", "") or "").strip()

            platform = str(c.get("platform", "") or "").strip().casefold()
            id_key = (platform, cid)
            author_key = (platform, author.casefold())
            # Record keys only after every rejection rule has passed.
            if self.by_comment_id and cid:
                if id_key in seen_ids:
                    stats["id_duplicates"] += 1
                    continue

            # 2. Text check
            if self.by_exact_text and text:
                if text in seen_texts:
                    stats["text_duplicates"] += 1
                    continue

            # 3. Author frequency limit
            if self.max_comments_per_author is not None and author:
                curr = author_counts.get(author_key, 0)
                if curr >= self.max_comments_per_author:
                    stats["author_limit_exceeded"] += 1
                    continue
            if self.by_comment_id and cid:
                seen_ids.add(id_key)
            if self.by_exact_text and text:
                seen_texts.add(text)
            if self.max_comments_per_author is not None and author:
                author_counts[author_key] = author_counts.get(author_key, 0) + 1
            kept.append(c)

        stats["total_removed"] = len(comments) - len(kept)
        stats["total_kept"] = len(kept)
        logger.info(
            f"Deduplication complete. Kept {len(kept)} / {len(comments)} comments "
            f"(removed {stats['total_removed']}: {stats['id_duplicates']} by ID, "
            f"{stats['text_duplicates']} by text, {stats['author_limit_exceeded']} by author limit)."
        )
        return kept, stats
