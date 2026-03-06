"""HTTP fetcher with rate limiting, retries with exponential backoff,
and optional Playwright fallback for JS-rendered pages."""

import asyncio
import hashlib
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_playwright_available: Optional[bool] = None

MAX_RETRIES = 3
BACKOFF_BASE = 1.5
BACKOFF_MAX = 15.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class FetcherService:
    """Fetch URLs with rate limiting, retries, and headless fallback."""

    def __init__(self):
        self.settings = get_settings()
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._last_fetch: dict[str, float] = {}
        self._rate = self.settings.default_rate_limit_per_domain

    def _domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def _throttle(self, domain: str, rate_limit: Optional[float] = None) -> None:
        rate = rate_limit or self._rate
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()
        async with self._domain_locks[domain]:
            loop = asyncio.get_running_loop()
            last = self._last_fetch.get(domain, 0)
            wait = max(0, (1.0 / rate) - (loop.time() - last))
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_fetch[domain] = loop.time()

    async def fetch(
        self,
        url: str,
        *,
        rate_limit: Optional[float] = None,
        use_browser: bool = False,
    ) -> Tuple[int, str, str, Optional[str]]:
        """Fetch URL with retries. Returns (status_code, body_text, content_type, content_hash)."""
        domain = self._domain(url)
        await self._throttle(domain, rate_limit)

        if use_browser:
            return await self._fetch_playwright(url)

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=self.settings.request_timeout_seconds,
                    headers={"User-Agent": self.settings.user_agent},
                    verify=self.settings.verify_ssl,
                ) as client:
                    resp = await client.get(url)

                    if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                        wait = min(BACKOFF_MAX, BACKOFF_BASE ** (attempt + 1))
                        logger.info(
                            "Fetch %s returned %d, retry %d/%d in %.1fs",
                            url[:80], resp.status_code, attempt + 1, MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    text = resp.text
                    content_type = resp.headers.get("content-type", "text/html") or "text/html"
                    if "application/rss" in content_type or "application/xml" in content_type:
                        content_type = "application/rss+xml"
                    h = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
                    if resp.status_code >= 400:
                        logger.warning("Fetch %s returned HTTP %d", url[:80], resp.status_code)
                    return resp.status_code, text, content_type, h

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, OSError) as e:
                last_exc = e
                if attempt < MAX_RETRIES:
                    wait = min(BACKOFF_MAX, BACKOFF_BASE ** (attempt + 1))
                    logger.info(
                        "Fetch %s failed (%s), retry %d/%d in %.1fs",
                        url[:80], type(e).__name__, attempt + 1, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.warning("Fetch %s failed after %d retries: %s", url[:80], MAX_RETRIES, e)
                raise
            except Exception as e:
                logger.warning("Fetch error %s: %s", url[:80], e)
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Fetch {url} failed: retries exhausted")

    async def _fetch_playwright(self, url: str) -> Tuple[int, str, str, Optional[str]]:
        global _playwright_available
        if _playwright_available is False:
            raise RuntimeError("Playwright not available on this platform")
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.settings.request_timeout_seconds * 1000,
                    )
                    text = await page.content()
                    content_type = "text/html"
                    h = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
                    return 200, text, content_type, h
                finally:
                    await browser.close()
        except NotImplementedError:
            _playwright_available = False
            logger.warning(
                "Playwright not supported on this platform (Windows asyncio limitation); skipping headless fallback"
            )
            raise
        except Exception as e:
            logger.debug("Playwright fallback failed for %s: %s", url[:80], e)
            raise
