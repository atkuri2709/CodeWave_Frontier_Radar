"""Extract main text and metadata from HTML, RSS, and optional PDF."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import feedparser
from bs4 import BeautifulSoup

try:
    from trafilatura import extract as trafilatura_extract
except ImportError:
    trafilatura_extract = None  # lxml.html.clean not installed; use BeautifulSoup only

logger = logging.getLogger(__name__)


class ExtractorService:
    """HTML -> text, RSS -> entries, metadata extraction."""

    def extract_html(
        self,
        html: str,
        url: str = "",
        selectors: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str, Optional[datetime], Dict[str, Any]]:
        """
        Extract main text and metadata from HTML.
        Returns (title, text, published_date, metadata).
        """
        soup = BeautifulSoup(html, "lxml")
        title = ""
        published_date: Optional[datetime] = None
        metadata: Dict[str, Any] = {}

        if selectors and selectors.get("title"):
            el = soup.select_one(selectors["title"])
            if el:
                title = el.get_text(strip=True)
        if not title:
            t = soup.find("title")
            title = t.get_text(strip=True) if t else ""

        # Try trafilatura for main content (if available)
        main_text = None
        if trafilatura_extract is not None:
            try:
                main_text = trafilatura_extract(
                    html, include_comments=False, include_tables=True
                )
            except Exception:
                pass
        if not main_text and selectors and selectors.get("content"):
            el = soup.select_one(selectors["content"])
            if el:
                main_text = el.get_text(separator="\n", strip=True)
        if not main_text:
            main_text = soup.get_text(separator="\n", strip=True)
        main_text = re.sub(r"\n{3,}", "\n\n", main_text).strip()

        # Date heuristics
        for tag in soup.find_all(
            ["time", "meta"],
            attrs={"property": ["article:published_time", "datePublished"]},
        ):
            d = tag.get("datetime") or tag.get("content")
            if d:
                published_date = self._parse_date(d)
                break
        if not published_date:
            for pattern in [
                r"\d{4}-\d{2}-\d{2}",
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}",
            ]:
                m = re.search(pattern, html)
                if m:
                    published_date = self._parse_date(m.group(0))
                    break

        metadata["title"] = title
        metadata["url"] = url
        metadata["word_count"] = len(main_text.split()) if main_text else 0
        if published_date:
            metadata["published_date"] = published_date.isoformat()

        desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if desc_tag and desc_tag.get("content"):
            metadata["description"] = desc_tag["content"][:500]

        author_tag = soup.find("meta", attrs={"name": "author"})
        if author_tag and author_tag.get("content"):
            metadata["author"] = author_tag["content"][:200]

        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            metadata["og_image"] = og_image["content"][:500]

        og_type = soup.find("meta", attrs={"property": "og:type"})
        if og_type and og_type.get("content"):
            metadata["og_type"] = og_type["content"]

        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            metadata["canonical_url"] = canonical["href"][:500]

        keywords_tag = soup.find("meta", attrs={"name": "keywords"})
        if keywords_tag and keywords_tag.get("content"):
            metadata["keywords"] = keywords_tag["content"][:500]

        lang = soup.find("html")
        if lang and lang.get("lang"):
            metadata["language"] = lang["lang"]

        return title, main_text, published_date, metadata

    def _parse_date(self, s: str) -> Optional[datetime]:
        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%d %b %Y",
            "%B %d, %Y",
        ):
            try:
                return datetime.strptime(
                    s.strip()[:26], fmt.replace("T%H:%M:%S%z", "T%H:%M:%S")[:19]
                )
            except Exception:
                continue
        return None

    def parse_rss(self, xml: str, url: str = "") -> List[Dict[str, Any]]:
        """Parse RSS/Atom feed and return list of entries."""
        feed = feedparser.parse(
            xml, response_headers={"content-type": "application/rss+xml"}
        )
        entries = []
        for e in feed.entries[:50]:
            published = None
            if hasattr(e, "published_parsed") and e.published_parsed:
                try:
                    published = datetime(*e.published_parsed[:6])
                except Exception:
                    pass
            link = e.get("link") or e.get("id") or url
            content = e.get("content") or e.get("summary") or ""
            if isinstance(content, list):
                content = content[0].get("value", "") if content else ""
            entries.append(
                {
                    "title": e.get("title", ""),
                    "link": link,
                    "published": published,
                    "summary": e.get("summary", ""),
                    "content": content,
                    "author": e.get("author", ""),
                }
            )
        return entries

    def parse_sitemap(self, body: str) -> List[str]:
        """
        Parse sitemap or sitemap index XML; returns list of <loc> URLs.
        Works for both <urlset> and <sitemapindex>.
        """
        urls: List[str] = []
        for parser in ("lxml", "html.parser"):
            try:
                soup = BeautifulSoup(body, parser)
                for loc in soup.find_all("loc"):
                    if loc is None:
                        continue
                    u = (loc.string or loc.get_text(strip=True) or "").strip()
                    if u:
                        urls.append(u)
                if urls:
                    break
            except Exception:
                continue
        return urls
