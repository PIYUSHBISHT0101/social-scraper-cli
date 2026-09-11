"""YouTube comment scraper supporting channels and video URLs."""
import re
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
import requests
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_POPULAR, SORT_BY_RECENT

from .base import BaseScraper

logger = logging.getLogger(__name__)

VIDEO_ID_REGEX = re.compile(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*")


class YouTubeScraper(BaseScraper):
    """Scrapes YouTube comments from channels and direct video URLs without API keys."""

    platform_name = "YouTube"

    def __init__(self, request_delay: float = 0.2):
        super().__init__(request_delay=request_delay)
        self.downloader = YoutubeCommentDownloader()

    def extract_video_id(self, url_or_id: str) -> Optional[str]:
        """Extract 11-char YouTube video ID."""
        clean = url_or_id.strip()
        if len(clean) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", clean):
            return clean
        match = VIDEO_ID_REGEX.search(clean)
        if match:
            return match.group(1)
        return None

    def get_channel_videos(self, channel_identifier: str, max_videos: int = 15) -> List[str]:
        """Discover recent video IDs from a channel page."""
        clean = channel_identifier.strip()
        if not clean.startswith("http"):
            if not clean.startswith("@"):
                clean = f"@{clean}"
            url = f"https://www.youtube.com/{clean}/videos"
        else:
            url = clean if "/videos" in clean else f"{clean.rstrip('/')}/videos"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        video_ids = []
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                raw_ids = re.findall(r'"videoId":"([0-9A-Za-z_-]{11})"', resp.text)
                # Deduplicate preserving order
                for vid in raw_ids:
                    if vid not in video_ids:
                        video_ids.append(vid)
                    if len(video_ids) >= max_videos:
                        break
        except Exception as e:
            logger.warning(f"Failed to fetch videos for channel {channel_identifier}: {e}")

        return video_ids

    def scrape_video_comments(
        self,
        video_id: str,
        channel_name: str,
        max_comments: int = 500,
        sort_by: int = SORT_BY_POPULAR,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        already_collected: int = 0,
        target_total: int = 500,
    ) -> List[Dict[str, Any]]:
        """Download comments for a single YouTube video ID."""
        comments = []
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            generator = self.downloader.get_comments(video_id, sort_by=sort_by)
            for c in generator:
                cid = c.get("cid", "")
                text = c.get("text", "")
                author = c.get("author", "")
                likes = c.get("votes", 0)
                time_str = c.get("time", "")

                try:
                    likes_int = int(str(likes).replace(",", "").strip() or 0)
                except Exception:
                    likes_int = 0

                normalized = self.normalize_comment(
                    comment_id=cid,
                    platform="YouTube",
                    source_name=channel_name,
                    target_id=video_id,
                    target_url=video_url,
                    comment_text=text,
                    author=author,
                    author_id="",
                    like_count=likes_int,
                    reply_count=0,
                    created_at=time_str,
                    source_url=f"https://www.youtube.com/watch?v={video_id}&lc={cid}",
                )
                normalized["collected_at"] = datetime.now(timezone.utc).isoformat()
                comments.append(normalized)

                if progress_callback:
                    progress_callback(channel_name, already_collected + len(comments), target_total)

                if len(comments) >= max_comments:
                    break

                if self.request_delay:
                    time.sleep(self.request_delay * 0.05)

        except Exception as e:
            logger.warning(f"Error scraping YouTube video {video_id}: {e}")

        return comments

    def scrape(
        self,
        targets: List[str],
        limit_per_target: int = 500,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape YouTube comments across multiple targets."""
        all_comments = []

        for target in targets:
            clean_target = target.strip()
            if not clean_target:
                continue

            vid_id = self.extract_video_id(clean_target)
            target_comments = []

            if vid_id:
                # Target is a direct video
                source_name = f"video_{vid_id}"
                target_comments = self.scrape_video_comments(
                    vid_id,
                    source_name,
                    max_comments=limit_per_target,
                    progress_callback=progress_callback,
                    already_collected=0,
                    target_total=limit_per_target,
                )
            else:
                # Target is a channel
                source_name = clean_target.lstrip("@")
                video_ids = self.get_channel_videos(clean_target, max_videos=15)
                if not video_ids:
                    logger.warning(f"No videos found for YouTube channel: {clean_target}")
                    continue

                comments_per_video = max(50, limit_per_target // len(video_ids) + 20)

                for vid in video_ids:
                    needed = limit_per_target - len(target_comments)
                    if needed <= 0:
                        break

                    vid_comments = self.scrape_video_comments(
                        vid,
                        source_name,
                        max_comments=min(needed, comments_per_video),
                        progress_callback=progress_callback,
                        already_collected=len(target_comments),
                        target_total=limit_per_target,
                    )
                    target_comments.extend(vid_comments)

            all_comments.extend(target_comments)

        return all_comments
