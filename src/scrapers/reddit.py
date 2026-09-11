"""Reddit comment scraper supporting subreddits and direct post URLs.

Uses PRAW (Python Reddit API Wrapper) as the primary scraping method.
Requires Reddit API credentials (client_id, client_secret) for reliable operation.
Falls back to public JSON endpoints if PRAW is not configured (may be blocked by Reddit).
"""
import os
import re
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
import requests

from .base import BaseScraper

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


class RedditScraper(BaseScraper):
    """Scrapes Reddit comments from subreddits and posts.
    
    Primary method: PRAW (official Reddit API via OAuth2).
    Fallback: Public .json endpoints (may be blocked by Reddit/Cloudflare).
    
    To use PRAW, provide client_id and client_secret from:
    https://www.reddit.com/prefs/apps (create a 'script' type app).
    """

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
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET", "")
        self.praw_client = None
        self._is_authenticated = False
        self._praw_available = False
        self.authenticated_user = ""

        # Auto-initialize PRAW if credentials available
        if self.client_id and self.client_secret:
            self._init_praw()
        elif username and password:
            self.authenticate(username, password, client_id, client_secret)

    def _init_praw(self, read_only: bool = True) -> bool:
        """Initialize PRAW Reddit client in read-only or authenticated mode."""
        try:
            import praw
            kwargs = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "user_agent": f"SocialScraperCLI/1.0 (by u/{self.username or 'anon'})",
            }
            if self.username and self.password:
                kwargs["username"] = self.username
                kwargs["password"] = self.password
                read_only = False

            r = praw.Reddit(**kwargs)

            if not read_only:
                # Verify authentication
                user = r.user.me()
                if user:
                    self.authenticated_user = str(user.name)
                    self._is_authenticated = True
            
            self.praw_client = r
            self._praw_available = True
            logger.info(f"PRAW initialized ({'authenticated' if self._is_authenticated else 'read-only'} mode)")
            return True
        except Exception as e:
            logger.warning(f"PRAW initialization failed: {e}")
            self._praw_available = False
            return False

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
        self.client_id = client_id or self.client_id or os.getenv("REDDIT_CLIENT_ID", "")
        self.client_secret = client_secret or self.client_secret or os.getenv("REDDIT_CLIENT_SECRET", "")

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
                    self._praw_available = True
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
                    return False, f"Reddit account u/{self.username} not found (Status {resp.status_code}). Note: Reddit API credentials (client_id, client_secret) are recommended."
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

    def extract_post_id_from_url(self, url: str) -> Optional[str]:
        """Extract Reddit post ID from a URL like /r/sub/comments/POST_ID/..."""
        match = re.search(r"/comments/([a-z0-9]+)", url)
        if match:
            return match.group(1)
        return None

    # ── PRAW-Based Methods (Primary) ──────────────────────────────────

    def _praw_get_subreddit_posts(self, subreddit: str, limit: int = 25, sort: str = "hot") -> List[dict]:
        """Fetch post metadata using PRAW."""
        if not self.praw_client:
            return []
        
        try:
            sub = self.praw_client.subreddit(subreddit)
            
            if sort == "hot":
                submissions = sub.hot(limit=limit)
            elif sort == "new":
                submissions = sub.new(limit=limit)
            elif sort == "top":
                submissions = sub.top(limit=limit, time_filter="week")
            else:
                submissions = sub.hot(limit=limit)
            
            posts = []
            for s in submissions:
                posts.append({
                    "post_id": s.id,
                    "title": s.title,
                    "permalink": f"https://www.reddit.com{s.permalink}",
                    "num_comments": s.num_comments,
                    "score": s.score,
                    "submission": s,  # Keep reference for comment extraction
                })
            return posts
        except Exception as e:
            logger.warning(f"PRAW get_subreddit_posts failed for r/{subreddit}: {e}")
            return []

    def _praw_scrape_post_comments(
        self,
        submission,
        subreddit_name: str,
        max_comments: int = 500,
    ) -> List[dict]:
        """Extract comments from a PRAW Submission object."""
        comments = []
        try:
            submission.comments.replace_more(limit=0)  # Skip "load more" to avoid rate limits
            all_comments = submission.comments.list()
            
            post_meta = {
                "post_id": submission.id,
                "title": submission.title,
                "permalink": f"https://www.reddit.com{submission.permalink}",
            }
            
            for c in all_comments:
                if not hasattr(c, "body"):
                    continue
                body = c.body
                if not body or body in ["[deleted]", "[removed]"]:
                    continue
                
                cid = c.id
                author = str(c.author) if c.author else "[deleted]"
                score = c.score
                created_dt = datetime.fromtimestamp(c.created_utc, tz=timezone.utc).isoformat() if c.created_utc else ""
                permalink = f"https://www.reddit.com{c.permalink}" if hasattr(c, "permalink") else post_meta["permalink"]
                
                normalized = self.normalize_comment(
                    comment_id=cid,
                    platform="Reddit",
                    source_name=f"r/{subreddit_name}",
                    target_id=post_meta.get("post_id", ""),
                    target_url=post_meta.get("permalink", ""),
                    comment_text=body,
                    author=author,
                    author_id=str(c.author_fullname) if hasattr(c, "author_fullname") and c.author_fullname else "",
                    like_count=score,
                    reply_count=0,
                    created_at=created_dt,
                    source_url=permalink,
                )
                normalized["collected_at"] = datetime.now(timezone.utc).isoformat()
                comments.append(normalized)
                
                if len(comments) >= max_comments:
                    break
                    
        except Exception as e:
            logger.warning(f"PRAW comment extraction error: {e}")
        
        return comments

    def _praw_scrape_post_url(self, post_url: str, subreddit_name: str, max_comments: int = 500) -> List[dict]:
        """Scrape comments from a direct post URL using PRAW."""
        if not self.praw_client:
            return []
        
        try:
            submission = self.praw_client.submission(url=post_url)
            return self._praw_scrape_post_comments(submission, subreddit_name, max_comments)
        except Exception as e:
            # Try extracting the post ID and using that
            post_id = self.extract_post_id_from_url(post_url)
            if post_id:
                try:
                    submission = self.praw_client.submission(id=post_id)
                    return self._praw_scrape_post_comments(submission, subreddit_name, max_comments)
                except Exception as e2:
                    logger.warning(f"PRAW post URL scrape failed for {post_url}: {e2}")
            else:
                logger.warning(f"PRAW post URL scrape failed for {post_url}: {e}")
            return []

    # ── Public JSON Fallback Methods ──────────────────────────────────

    def fetch_json(self, url: str) -> Optional[Any]:
        """Fetch JSON data from Reddit (fallback when PRAW unavailable).
        
        WARNING: Reddit has blocked most .json endpoint access since mid-2025.
        This method will likely return None. Use PRAW-based methods instead.
        """
        url_clean = url if url.endswith(".json") else f"{url.rstrip('/')}.json"
        
        # Try curl_cffi with browser impersonation
        try:
            from curl_cffi import requests as cffi_requests
            resp = cffi_requests.get(url_clean, headers=HEADERS, impersonate="chrome124", timeout=12)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning("Reddit 429 Rate Limit. Sleeping 2s...")
                time.sleep(2.0)
            else:
                logger.debug(f"Reddit JSON endpoint returned {resp.status_code} for {url_clean}")
        except Exception as e:
            logger.debug(f"curl_cffi failed for {url_clean}: {e}")

        # Fallback to standard requests
        try:
            resp = requests.get(url_clean, headers=HEADERS, timeout=12)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.debug(f"requests fallback returned {resp.status_code} for {url_clean}")
        except Exception as e:
            logger.debug(f"requests fallback failed for {url_clean}: {e}")
        
        return None

    def _json_get_subreddit_posts(self, subreddit: str, limit: int = 25, sort: str = "hot") -> List[dict]:
        """Fetch post metadata via public JSON endpoint (fallback)."""
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

    def _json_scrape_post_comments(self, post_url: str, subreddit_name: str, max_comments: int = 500) -> List[dict]:
        """Download comments from a post URL via JSON endpoint (fallback)."""
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
        comments = self._extract_comments_recursive(comment_children, post_meta, subreddit_name)
        return comments[:max_comments]

    def _extract_comments_recursive(self, children: list, post_data: dict, subreddit_name: str) -> List[dict]:
        """Flatten nested Reddit comment tree from JSON data."""
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
                extracted.extend(self._extract_comments_recursive(sub_children, post_data, subreddit_name))

        return extracted

    # ── Unified Scrape Interface ──────────────────────────────────────

    def get_subreddit_posts(self, subreddit: str, limit: int = 25, sort: str = "hot") -> List[dict]:
        """Fetch posts from a subreddit. Uses PRAW first, then JSON fallback."""
        if self._praw_available:
            posts = self._praw_get_subreddit_posts(subreddit, limit, sort)
            if posts:
                return posts
            logger.info(f"PRAW returned no posts for r/{subreddit}, trying JSON fallback...")
        
        return self._json_get_subreddit_posts(subreddit, limit, sort)

    def scrape_post_comments(self, post_url_or_submission, subreddit_name: str, max_comments: int = 500) -> List[dict]:
        """Scrape comments from a post. Accepts URL string or PRAW Submission."""
        # If we got a PRAW submission object (from _praw_get_subreddit_posts)
        if hasattr(post_url_or_submission, 'id') and hasattr(post_url_or_submission, 'comments'):
            return self._praw_scrape_post_comments(post_url_or_submission, subreddit_name, max_comments)
        
        post_url = str(post_url_or_submission)
        
        # Try PRAW first
        if self._praw_available:
            comments = self._praw_scrape_post_url(post_url, subreddit_name, max_comments)
            if comments:
                return comments
            logger.debug(f"PRAW returned no comments for {post_url}, trying JSON fallback...")
        
        # JSON fallback
        return self._json_scrape_post_comments(post_url, subreddit_name, max_comments)

    def scrape(
        self,
        targets: List[str],
        limit_per_target: int = 500,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape Reddit comments across target subreddits or post URLs."""
        all_comments = []

        # Check if we have a working scraping method
        if not self._praw_available:
            logger.warning(
                "PRAW not configured. Reddit has blocked public .json endpoints (403 Forbidden). "
                "For reliable Reddit scraping, provide REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET. "
                "Get free API credentials at: https://www.reddit.com/prefs/apps"
            )

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
                    if not self._praw_available:
                        logger.error(
                            f"No posts found for r/{sub_name}. Reddit blocks unauthenticated JSON API access. "
                            f"Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables, "
                            f"or provide them in the wizard. Get them at: https://www.reddit.com/prefs/apps"
                        )
                    else:
                        logger.warning(f"No posts found for r/{sub_name}")
                    continue

                for p in posts:
                    needed = limit_per_target - len(target_comments)
                    if needed <= 0:
                        break

                    # Use PRAW submission object directly if available
                    source = p.get("submission", p["permalink"])
                    post_comments = self.scrape_post_comments(source, sub_name, max_comments=needed)
                    target_comments.extend(post_comments)

                    if progress_callback:
                        progress_callback(f"r/{sub_name}", len(target_comments), limit_per_target)

                    time.sleep(self.request_delay)

            all_comments.extend(target_comments)

        return all_comments
