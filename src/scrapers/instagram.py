"""Instagram comment scraper supporting profiles and direct post URLs."""
import os
import re
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
from dotenv import load_dotenv

from .base import BaseScraper

logger = logging.getLogger(__name__)


class InstagramScraper(BaseScraper):
    """Scrapes Instagram comments with sessionid authentication and rate-limit handling."""

    platform_name = "Instagram"

    def __init__(
        self,
        session_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        request_delay: float = 0.3
    ):
        super().__init__(request_delay=request_delay)
        if os.path.exists(".env"):
            load_dotenv(".env")

        self.session_id = session_id or os.getenv("INSTAGRAM_SESSION_ID", "")
        self.username = username
        self.password = password
        self.ig = None
        self._is_authenticated = False
        self.authenticated_user = ""

        if self.session_id:
            self.login_with_session_id(self.session_id)
        elif self.username and self.password:
            self.login_with_credentials(self.username, self.password)

    def login_with_session_id(self, session_id: str) -> tuple[bool, str]:
        """Authenticate using sessionid cookie and verify account."""
        clean_sid = (session_id or "").strip()
        if not clean_sid:
            return False, "Session ID cannot be empty."

        self.session_id = clean_sid
        try:
            from instagrapi import Client
            self.ig = Client()
            self.ig.delay_range = [0.1, 0.3]
            self.ig.login_by_sessionid(self.session_id)
            # Verify session
            user_info = self.ig.account_info()
            self.authenticated_user = user_info.username if hasattr(user_info, "username") else "User"
            self._is_authenticated = True
            return True, f"Successfully authenticated as @{self.authenticated_user}"
        except Exception as e:
            self._is_authenticated = False
            return False, f"Session authentication failed: {str(e)}"

    def login_with_credentials(self, username: str, password: str) -> tuple[bool, str]:
        """Authenticate using Instagram username and password."""
        self.username = (username or "").strip().lstrip("@")
        self.password = password or ""
        if not self.username or not self.password:
            return False, "Both username and password must be provided."

        try:
            from instagrapi import Client
            self.ig = Client()
            self.ig.delay_range = [0.1, 0.3]
            self.ig.login(self.username, self.password)
            self.authenticated_user = self.username
            self._is_authenticated = True
            return True, f"Successfully logged in as @{self.authenticated_user}"
        except Exception as e:
            self._is_authenticated = False
            return False, f"Login failed: {str(e)}"

    def authenticate_with_token(self, session_id: str) -> bool:
        """Compatibility helper."""
        success, _ = self.login_with_session_id(session_id)
        return success

    def extract_shortcode(self, target: str) -> Optional[str]:
        """Extract Instagram post shortcode if target is a post URL."""
        match = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", target)
        if match:
            return match.group(1)
        return None

    def clean_username(self, target: str) -> str:
        """Extract clean Instagram username."""
        clean = target.strip().rstrip("/")
        if "instagram.com/" in clean:
            match = re.search(r"instagram\.com/([^/?#]+)", clean)
            if match and match.group(1) not in ["p", "reel", "stories", "explore"]:
                return match.group(1)
        return clean.lstrip("@")

    def scrape_post_comments(
        self,
        media_id_or_code: str,
        account_name: str,
        max_comments: int = 500,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        already_collected: int = 0,
        target_total: int = 500,
    ) -> List[Dict[str, Any]]:
        """Download comments for an Instagram post."""
        if not self.ig or not self._is_authenticated:
            logger.warning("Instagram authentication required to fetch post comments.")
            return []

        comments = []
        try:
            # Resolve media PK if shortcode passed
            if not str(media_id_or_code).isdigit():
                media_pk = self.ig.media_pk_from_code(media_id_or_code)
                shortcode = media_id_or_code
            else:
                media_pk = int(media_id_or_code)
                shortcode = self.ig.media_info(media_pk).code

            ig_comments = self.ig.media_comments(media_pk, amount=max_comments)
            for c in ig_comments:
                cid = str(c.pk)
                text = c.text or ""
                author = c.user.username if c.user else ""
                author_id = str(c.user.pk) if c.user else ""
                likes = getattr(c, "comment_like_count", getattr(c, "like_count", 0))
                created_dt = c.created_at_utc.isoformat() if hasattr(c, "created_at_utc") and c.created_at_utc else ""

                normalized = self.normalize_comment(
                    comment_id=cid,
                    platform="Instagram",
                    source_name=f"@{account_name}",
                    target_id=str(media_pk),
                    target_url=f"https://www.instagram.com/p/{shortcode}/",
                    comment_text=text,
                    author=author,
                    author_id=author_id,
                    like_count=likes,
                    reply_count=0,
                    created_at=created_dt,
                    source_url=f"https://www.instagram.com/p/{shortcode}/c/{cid}/",
                )
                normalized["collected_at"] = datetime.now(timezone.utc).isoformat()
                comments.append(normalized)

                if progress_callback:
                    progress_callback(f"@{account_name}", already_collected + len(comments), target_total)

                if len(comments) >= max_comments:
                    break

        except Exception as e:
            logger.warning(f"Error fetching Instagram comments for {media_id_or_code}: {e}")

        return comments

    def scrape(
        self,
        targets: List[str],
        limit_per_target: int = 500,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape Instagram comments across target profiles or post URLs."""
        if not self._is_authenticated:
            logger.error("Instagram session is not authenticated. Please provide INSTAGRAM_SESSION_ID.")
            return []

        all_comments = []

        for target in targets:
            clean_target = target.strip()
            if not clean_target:
                continue

            target_comments = []
            shortcode = self.extract_shortcode(clean_target)

            if shortcode:
                # Direct post URL
                account_name = "post"
                target_comments = self.scrape_post_comments(
                    shortcode,
                    account_name,
                    max_comments=limit_per_target,
                    progress_callback=progress_callback,
                    already_collected=0,
                    target_total=limit_per_target,
                )
            else:
                # Profile handle
                username = self.clean_username(clean_target)
                try:
                    user_id = self.ig.user_id_from_username(username)
                    medias = self.ig.user_medias(user_id, amount=15)
                    if not medias:
                        logger.warning(f"No posts found for Instagram profile @{username}")
                        continue

                    comments_per_post = max(50, limit_per_target // len(medias) + 20)

                    for m in medias:
                        needed = limit_per_target - len(target_comments)
                        if needed <= 0:
                            break

                        post_comments = self.scrape_post_comments(
                            str(m.pk),
                            username,
                            max_comments=min(needed, comments_per_post),
                            progress_callback=progress_callback,
                            already_collected=len(target_comments),
                            target_total=limit_per_target,
                        )
                        target_comments.extend(post_comments)
                        time.sleep(self.request_delay)

                except Exception as e:
                    logger.warning(f"Error scraping Instagram profile @{username}: {e}")

            all_comments.extend(target_comments)

        return all_comments
