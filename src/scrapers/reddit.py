"""Reddit comment scraper supporting subreddits and direct post URLs."""
import re
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
from curl_cffi import requests as cffi_requests
import requests

from .base import BaseScraper

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


class RedditScraper(BaseScraper):
    """Scrapes Reddit comments from subreddits and posts with optional credential verification."""

    platform_name = "Reddit"

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        request_delay: float = 0.5
    ):
        super().__init__(request_delay=request_delay)
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.praw_client = None
        self._is_authenticated = False
        self.authenticated_user = ""

        if username and password:
            self.authenticate(username, password, client_id, client_secret)

    def authenticate(
        self,
        username: str,
        password: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Verify Reddit credentials live against Reddit API."""
        self.username = username.strip().lstrip("u/")
        self.password = password
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET", "")

        try:
            import praw
            if self.client_id and self.client_secret:
                r = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    username=self.username,
                    password=self.password,
                    user_agent=f"SocialScraperCLI/1.0 (by u/{self.username})",
                )
                user = r.user.me()
                if user:
                    self.praw_client = r
                    self._is_authenticated = True
                    self.authenticated_user = str(user.name)
                    return True, f"Successfully verified as u/{self.authenticated_user}"
                else:
                    return False, "Could not verify Reddit user (credentials rejected)"
            else:
                # If client_id/secret not provided, verify user profile exists publicly
                check_url = f"https://www.reddit.com/user/{self.username}/about.json"
                resp = requests.get(check_url, headers=HEADERS, timeout=8)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    self._is_authenticated = True
                    self.authenticated_user = data.get("name", self.username)
                    return True, f"Verified public Reddit account: u/{self.authenticated_user}"
                else:
                    return False, f"Reddit account u/{self.username} not found (Status {resp.status_code})"
        except Exception as e:
            self._is_authenticated = False
            return False, f"Reddit verification error: {str(e)}"

    def clean_subreddit_name(self, target: str) -> str:
        """Extract clean subreddit name."""
        clean = target.strip().rstrip("/")
        if "reddit.com/r/" in clean:
            match = re.search(r"reddit\.com/r/([^/?#]+)", clean)
            if match:
                return match.group(1)
        if clean.startswith("r/"):
            return clean[2:]
        return clean

    def is_post_url(self, target: str) -> bool:
        """Check if target is a direct post link."""
        return "reddit.com/r/" in target and "/comments/" in target

    def fetch_json(self, url: str) -> Optional[Any]:
        """Fetch JSON data from Reddit with browser impersonation."""
        url_clean = url if url.endswith(".json") else f"{url.rstrip('/')}.json"
        try:
            resp = cffi_requests.get(url_clean, headers=HEADERS, impersonate="chrome124", timeout=12)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning("Reddit 429 Rate Limit. Sleeping 2s...")
                time.sleep(2.0)
        except Exception as e:
            # Fallback to standard requests
            try:
                resp = requests.get(url_clean, headers=HEADERS, timeout=12)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                logger.warning(f"Error fetching Reddit URL {url}: {e}")
        return None

    def get_subreddit_posts(self, subreddit: str, limit: int = 25, sort: str = "hot") -> List[dict]:
        """Fetch post metadata from a subreddit."""
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
        data = self.fetch_json(url)
        posts = []
        if data and isinstance(data, dict):
            children = data.get("data", {}).get("children", [])
            for c in children:
                p = c.get("data", {})
                posts.append({
                    "post_id": p.get("id"),
                    "title": p.get("title", ""),
                    "permalink": f"https://www.reddit.com{p.get('permalink')}",
                    "num_comments": p.get("num_comments", 0),
                    "score": p.get("score", 0),
                })
        return posts

    def extract_comments_recursive(self, children: list, post_data: dict, subreddit_name: str) -> List[dict]:
        """Flatten nested Reddit comment tree."""
        extracted = []
        for c in children:
            if c.get("kind") != "t1":
                continue
            data = c.get("data", {})
            body = data.get("body", "")
            if not body or body in ["[deleted]", "[removed]"]:
                continue

            cid = data.get("id", "")
            author = data.get("author", "[deleted]")
            score = data.get("score", 0)
            created_utc = data.get("created_utc", 0)
            created_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat() if created_utc else ""
            permalink = f"https://www.reddit.com{data.get('permalink')}" if data.get("permalink") else post_data.get("permalink", "")

            normalized = self.normalize_comment(
                comment_id=cid,
                platform="Reddit",
                source_name=f"r/{subreddit_name}",
                target_id=post_data.get("post_id", ""),
                target_url=post_data.get("permalink", ""),
                comment_text=body,
                author=author,
                author_id=data.get("author_fullname", ""),
                like_count=score,
                reply_count=0,
                created_at=created_dt,
                source_url=permalink,
            )
            normalized["collected_at"] = datetime.now(timezone.utc).isoformat()
            extracted.append(normalized)

            # Traverse replies if any
            replies = data.get("replies")
            if isinstance(replies, dict):
                sub_children = replies.get("data", {}).get("children", [])
                extracted.extend(self.extract_comments_recursive(sub_children, post_data, subreddit_name))

        return extracted

    def scrape_post_comments(self, post_url: str, subreddit_name: str, max_comments: int = 500) -> List[dict]:
        """Download comments for a single Reddit post URL."""
        data = self.fetch_json(post_url)
        if not data or not isinstance(data, list) or len(data) < 2:
            return []

        post_meta = {}
        if data[0].get("data", {}).get("children"):
            p_data = data[0]["data"]["children"][0].get("data", {})
            post_meta = {
                "post_id": p_data.get("id"),
                "title": p_data.get("title", ""),
                "permalink": f"https://www.reddit.com{p_data.get('permalink')}",
            }

        comment_children = data[1].get("data", {}).get("children", [])
        comments = self.extract_comments_recursive(comment_children, post_meta, subreddit_name)
        return comments[:max_comments]

    def scrape(
        self,
        targets: List[str],
        limit_per_target: int = 500,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape Reddit comments across target subreddits or post URLs."""
        all_comments = []

        for target in targets:
            clean_target = target.strip()
            if not clean_target:
                continue

            target_comments = []

            if self.is_post_url(clean_target):
                sub_name = self.clean_subreddit_name(clean_target)
                target_comments = self.scrape_post_comments(clean_target, sub_name, max_comments=limit_per_target)
                if progress_callback:
                    progress_callback(f"r/{sub_name}", len(target_comments), limit_per_target)
            else:
                sub_name = self.clean_subreddit_name(clean_target)
                posts = self.get_subreddit_posts(sub_name, limit=25, sort="hot")
                if not posts:
                    logger.warning(f"No posts found for r/{sub_name}")
                    continue

                for p in posts:
                    needed = limit_per_target - len(target_comments)
                    if needed <= 0:
                        break

                    post_comments = self.scrape_post_comments(p["permalink"], sub_name, max_comments=needed)
                    target_comments.extend(post_comments)

                    if progress_callback:
                        progress_callback(f"r/{sub_name}", len(target_comments), limit_per_target)

                    time.sleep(self.request_delay)

            all_comments.extend(target_comments)

        return all_comments
