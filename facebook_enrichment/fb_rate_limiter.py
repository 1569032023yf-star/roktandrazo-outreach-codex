"""Facebook Rate Limiter — global safety controller for browser-based page visits.

Design:
- Single instance controls all page timing
- Random intervals within configured ranges
- Automatic cooldown pauses every N pages
- Page cache to avoid re-opening recently visited URLs
- Block signal detection: stops whole round on login/captcha/access-denied
- Max pages per round

No network calls. No DB access. Pure timing and state control.
"""
from __future__ import annotations

import random
import time
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class RateLimitConfig:
    """All timing ranges in seconds. Each value is (min, max)."""
    page_load_wait: tuple[float, float] = (8.0, 10.0)    # After page navigates, before reading
    pre_about_dwell: tuple[float, float] = (2.0, 5.0)     # Before clicking About/reading details
    between_pages: tuple[float, float] = (5.0, 12.0)      # Between finishing one page and starting next
    cooldown_interval: int = 5                             # Pause after every N pages
    cooldown_duration: tuple[float, float] = (30.0, 60.0)  # Cooldown pause range
    max_pages_per_round: int = 20                          # Hard stop after this many pages
    cache_ttl: int = 3600                                  # Cache entries expire after 1 hour


class FBRateLimiter:
    """Controls pacing of Facebook page visits.

    Usage:
        limiter = FBRateLimiter()
        limiter.start_round()

        for each page:
            if limiter.should_stop():
                break
            if limiter.is_cached(fb_url):
                continue
            limiter.before_page_load()
            page.goto(fb_url)
            limiter.after_page_load()
            # ... read page ...
            limiter.before_detail()
            # ... click About, read details ...
            limiter.after_page(fb_url)
    """

    def __init__(self, config: RateLimitConfig = None):
        self.cfg = config or RateLimitConfig()
        self._pages_done: int = 0
        self._rounds: int = 0
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._blocked: bool = False
        self._block_reason: str = ""
        self._total_wait: float = 0.0

    def start_round(self):
        """Call once at the beginning of a batch."""
        self._pages_done = 0
        self._blocked = False
        self._block_reason = ""
        self._total_wait = 0.0

    def should_stop(self) -> bool:
        """Check if we should stop processing (block signals or max pages)."""
        if self._blocked:
            return True
        if self._pages_done >= self.cfg.max_pages_per_round:
            print(f"  [LIMITER] Max pages ({self.cfg.max_pages_per_round}) reached. Stopping round.")
            return True
        return False

    def block(self, reason: str):
        """Signal a permanent block for this round (login, captcha, access denied)."""
        self._blocked = True
        self._block_reason = reason
        print(f"  [LIMITER] BLOCKED: {reason}. Stopping round.")

    @property
    def blocked(self) -> bool:
        return self._blocked

    @property
    def block_reason(self) -> str:
        return self._block_reason

    @property
    def pages_done(self) -> int:
        return self._pages_done

    @property
    def total_wait(self) -> float:
        return self._total_wait

    # --- Cache ---

    def is_cached(self, url: str) -> bool:
        """Check if URL was visited recently. Auto-expires old entries."""
        self._expire_cache()
        return url in self._cache

    def _expire_cache(self):
        now = time.time()
        expired = [k for k, ts in self._cache.items() if now - ts > self.cfg.cache_ttl]
        for k in expired:
            del self._cache[k]

    # --- Timing ---

    def _rand(self, rng: tuple[float, float]) -> float:
        return random.uniform(*rng)

    def before_page_load(self):
        """Wait before loading a new page."""
        if self._pages_done > 0:
            wait = self._rand(self.cfg.between_pages)
            self._total_wait += wait
            self._sleep(wait, "between pages")

        # Cooldown check
        if self._pages_done > 0 and self._pages_done % self.cfg.cooldown_interval == 0:
            wait = self._rand(self.cfg.cooldown_duration)
            self._total_wait += wait
            self._sleep(wait, "cooldown")

    def after_page_load(self):
        """Wait after page loads, before reading content."""
        wait = self._rand(self.cfg.page_load_wait)
        self._total_wait += wait
        self._sleep(wait, "page load settle")

    def before_detail(self):
        """Wait before clicking About or reading detailed sections."""
        wait = self._rand(self.cfg.pre_about_dwell)
        self._total_wait += wait
        self._sleep(wait, "pre-detail dwell")

    def after_page(self, url: str):
        """Mark page as done and cache it."""
        self._pages_done += 1
        self._cache[url] = time.time()
        # Keep cache bounded
        while len(self._cache) > 100:
            self._cache.popitem(last=False)

    def _sleep(self, seconds: float, label: str):
        print(f"  [LIMITER] Waiting {seconds:.1f}s ({label})...")
        time.sleep(seconds)

    # --- Stats ---

    def stats(self) -> dict:
        return {
            "pages_processed": self._pages_done,
            "blocked": self._blocked,
            "block_reason": self._block_reason,
            "total_wait_seconds": round(self._total_wait, 1),
            "cached_urls": len(self._cache),
        }
