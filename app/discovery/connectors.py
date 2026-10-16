
import asyncio
import logging
import ipaddress
import socket
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin

import httpx


logger = logging.getLogger(__name__)

USER_AGENT = "SolveEaseIntentForge/1.0 (public signal discovery)"
MAX_TEXT_LENGTH = 5000
MAX_RETRIES = 2

REDDIT_BASE = "https://www.reddit.com"
GITHUB_API = "https://api.github.com"

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_public_https_url(url: str) -> bool:
    """
    Basic URL guard for configured public feeds.
    Configure trusted feed hosts; do not accept arbitrary user URLs.
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme != "https" or not parsed.hostname:
            return False

        if parsed.username or parsed.password:
            return False

        host = parsed.hostname.lower()

        if host in {"localhost", "localhost.localdomain"}:
            return False

        try:
            ip = ipaddress.ip_address(host)
            if not ip.is_global:
                return False
        except ValueError:
            # A DNS hostname still requires network-level SSRF protection.
            pass

        return True
    except (ValueError, TypeError):
        return False


async def request_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 8.0,
) -> httpx.Response | None:
    """Retry transient HTTP failures without hiding final errors."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
            )

            if response.status_code == 200:
                return response

            retryable = (
                response.status_code == 429
                or 500 <= response.status_code < 600
            )

            if not retryable:
                logger.warning(
                    "Source returned HTTP %s: %s",
                    response.status_code,
                    url,
                )
                return None

            if attempt < MAX_RETRIES:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = min(float(retry_after), 15.0)
                except (TypeError, ValueError):
                    delay = 1.0 * (2 ** attempt)

                await asyncio.sleep(max(0.0, delay))

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning("Network error fetching %s: %s", url, exc)

            if attempt < MAX_RETRIES:
                await asyncio.sleep(1.0 * (2 ** attempt))

        except httpx.HTTPError as exc:
            logger.warning("HTTP client error fetching %s: %s", url, exc)
            return None

    return None


def normalize_signal(
    *,
    signal_id: str,
    source: str,
    source_type: str,
    title: str,
    body: str,
    url: str,
    timestamp: str | None = None,
) -> dict:
    """Create a consistent record for downstream processing."""
    title = (title or "").strip()
    body = (body or "").strip()

    return {
        "signal_id": signal_id,
        "source": source,
        "source_type": source_type,
        "title": title[:1000],
        "text": f"{title} — {body}"[:MAX_TEXT_LENGTH],
        "url": url,
        "timestamp": timestamp or utc_now(),
        "fetched_at": utc_now(),
    }


async def fetch_reddit_json(
    client: httpx.AsyncClient,
    subreddit: str,
) -> list[dict]:
    signals = []

    # Prevent malformed subreddit paths.
    if not subreddit or not subreddit.replace("_", "").isalnum():
        logger.warning("Invalid subreddit name: %r", subreddit)
        return signals

    seen_ids = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    for sort_type in ("new", "hot", "rising"):
        url = f"{REDDIT_BASE}/r/{subreddit}/{sort_type}.json"

        response = await request_with_retries(
            client,
            url,
            params={"limit": 30, "raw_json": 1},
            headers=headers,
            timeout=8.0,
        )

        if response is None:
            continue

        try:
            payload = response.json()
            posts = payload.get("data", {}).get("children", [])

            for post in posts:
                item = post.get("data") or {}
                post_id = item.get("id")

                if not post_id or post_id in seen_ids:
                    continue

                title = item.get("title") or ""
                body = item.get("selftext") or ""

                if len(title.strip()) <= 3:
                    continue

                permalink = item.get("permalink") or ""
                post_url = urljoin(REDDIT_BASE, permalink)

                seen_ids.add(post_id)

                signals.append(
                    normalize_signal(
                        signal_id=f"reddit:{post_id}",
                        source=f"Reddit r/{subreddit}",
                        source_type="reddit",
                        title=title,
                        body=body[:4000],
                        url=post_url,
                        timestamp=(
                            datetime.fromtimestamp(
                                item["created_utc"],
                                timezone.utc,
                            ).isoformat()
                            if isinstance(
                                item.get("created_utc"), (int, float)
                            )
                            else None
                        ),
                    )
                )

        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            logger.warning("Could not parse Reddit response: %s", exc)

    return signals


def _child_text(element, name: str, namespace: str = "") -> str:
    child = element.find(f"{namespace}{name}")

    if child is None:
        return ""

    return "".join(child.itertext()).strip()


def _rss_link(entry, feed_url: str) -> str:
    # RSS link is commonly plain text; Atom link is an href attribute.
    link = entry.find(f"{ATOM_NS}link")

    if link is not None:
        href = link.get("href")
        if href:
            return urljoin(feed_url, href)

    rss_link = _child_text(entry, "link")
    return urljoin(feed_url, rss_link) if rss_link else feed_url


async def fetch_rss_feed(
    client: httpx.AsyncClient,
    url: str,
    source_name: str,
) -> list[dict]:
    signals = []

    if not safe_public_https_url(url):
        logger.warning("Rejected untrusted RSS URL: %s", url)
        return signals

    response = await request_with_retries(
        client,
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=10.0,
    )

    if response is None:
        return signals

    try:
        # XML is treated as untrusted input. For higher-risk deployments,
        # use a hardened XML parser and restrict feed size.
        if len(response.content) > 2_000_000:
            logger.warning("RSS feed too large: %s", url)
            return signals

        root = ET.fromstring(response.content)

        entries = root.findall(f".//{ATOM_NS}entry")
        if not entries:
            entries = root.findall(".//item")

        seen_ids = set()

        for entry in entries:
            title = (
                _child_text(entry, "title", ATOM_NS)
                or _child_text(entry, "title")
            )

            body = (
                _child_text(entry, "summary", ATOM_NS)
                or _child_text(entry, "content", ATOM_NS)
                or _child_text(entry, "description")
            )

            entry_id = (
                _child_text(entry, "id", ATOM_NS)
                or _child_text(entry, "guid")
            )

            entry_url = _rss_link(entry, url)
            stable_id = entry_id or entry_url

            if len(title.strip()) <= 3 or stable_id in seen_ids:
                continue

            seen_ids.add(stable_id)

            published = (
                _child_text(entry, "published", ATOM_NS)
                or _child_text(entry, "updated", ATOM_NS)
                or _child_text(entry, "pubDate")
            )

            signals.append(
                normalize_signal(
                    signal_id=f"rss:{source_name}:{stable_id}",
                    source=source_name,
                    source_type="rss",
                    title=title,
                    body=body[:4000],
                    url=entry_url,
                    timestamp=published or None,
                )
            )

    except ET.ParseError as exc:
        logger.warning("Invalid RSS/XML from %s: %s", url, exc)
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("Could not process feed %s: %s", url, exc)

    return signals


async def fetch_github_issues_deep(
    client: httpx.AsyncClient,
    token: str | None = None,
) -> list[dict]:
    signals = []

    queries = [
        "shopify checkout",
        "woocommerce webhook",
        "stripe webhook error",
        "google merchant feed",
        "affiliate tracking",
        "seo schema bug",
    ]

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    seen_ids = set()

    for query in queries:
        response = await request_with_retries(
            client,
            f"{GITHUB_API}/search/issues",
            params={
                "q": f"{query} is:issue is:open",
                "per_page": 20,
                "sort": "updated",
                "order": "desc",
            },
            headers=headers,
            timeout=10.0,
        )

        if response is None:
            continue

        try:
            payload = response.json()

            for item in payload.get("items", []):
                issue_id = item.get("id")
                issue_url = item.get("html_url") or ""

                if not issue_id or issue_id in seen_ids:
                    continue

                title = item.get("title") or ""
                body = item.get("body") or ""

                if len(title.strip()) <= 3:
                    continue

                seen_ids.add(issue_id)

                signals.append(
                    normalize_signal(
                        signal_id=f"github:{issue_id}",
                        source="GitHub Issues",
                        source_type="github",
                        title=title,
                        body=body[:4000],
                        url=issue_url,
                        timestamp=item.get("updated_at"),
                    )
                )

        except (ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "Could not parse GitHub search for %r: %s",
                query,
                exc,
            )

    return signals
