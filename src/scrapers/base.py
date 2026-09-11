"""Base scraper abstract interface."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable, Optional


class BaseScraper(ABC):
    """Abstract base class for platform scrapers."""

    platform_name: str = "Base"

    def __init__(self, request_delay: float = 0.5):
        self.request_delay = request_delay

    @abstractmethod
    def scrape(
        self,
        targets: List[str],
        limit_per_target: int = 500,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape comments for a list of targets.
        
        Args:
            targets: List of channels, subreddits, profiles, or specific URLs.
            limit_per_target: Max comments to fetch per target.
            progress_callback: Optional callback func(target, current, total).
            
        Returns:
            List of normalized comment dictionaries.
        """
        pass

    def normalize_comment(
        self,
        comment_id: str,
        platform: str,
        source_name: str,
        target_id: str,
        target_url: str,
        comment_text: str,
        author: str = "",
        author_id: str = "",
        like_count: int = 0,
        reply_count: int = 0,
        created_at: str = "",
        source_url: str = "",
    ) -> Dict[str, Any]:
        """Produce standardized comment record."""
        try:
            parsed_likes = int(str(like_count or 0).replace(",", "").strip())
        except (ValueError, TypeError):
            parsed_likes = 0

        try:
            parsed_replies = int(str(reply_count or 0).replace(",", "").strip())
        except (ValueError, TypeError):
            parsed_replies = 0

        return {
            "comment_id": str(comment_id),
            "platform": platform,
            "source_name": source_name,
            "target_id": str(target_id),
            "target_url": target_url,
            "comment": comment_text,
            "author": author,
            "author_id": str(author_id),
            "like_count": parsed_likes,
            "reply_count": parsed_replies,
            "created_at": str(created_at or ""),
            "source_url": source_url or target_url,
        }
