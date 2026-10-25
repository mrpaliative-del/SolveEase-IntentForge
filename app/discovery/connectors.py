import asyncio
import random
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import httpx
from app.discovery.filters import evaluate_intent

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "SolveEaseMultiEngine/3.1 (+https://market-alert-dzas.onrender.com)",
]

class FeedScanner:
    """
    Multi-Vector Live Telemetry Ingestion Engine.
    Sources:
    1. Reddit JSON Feeds (Subreddit streams)
    2. GitHub Public Issues API
    3. Stack Overflow API (Tagged bug questions)
    4. Dev.to Technical Discussions API
    5. Developer Community RSS / Atom Feeds
    """

    @staticmethod
    def _get_headers() -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, application/xml, text/xml, */*"
        }

    @classmethod
    async def fetch_reddit_intents(cls, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        intents = []
        subreddits = ["shopify", "woocommerce", "webdev", "FastAPI", "affiliatemarketing", "devops", "sysadmin"]
        
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=15"
            try:
                resp = await client.get(url, headers=cls._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    for post in posts:
                        pdata = post.get("data", {})
                        title = pdata.get("title", "")
                        selftext = pdata.get("selftext", "")
                        permalink = f"https://reddit.com{pdata.get('permalink', '')}"
                        
                        eval_res = evaluate_intent(title, selftext)
                        if eval_res["matched"]:
                            intents.append({
                                "task_hash": eval_res["task_hash"],
                                "domain": eval_res["domain"],
                                "title": title[:200],
                                "snippet": selftext[:400] if selftext else title[:400],
                                "source": permalink,
                                "price": eval_res["price"]
                            })
                await asyncio.sleep(0.8)
            except Exception:
                continue
        return intents

    @classmethod
    async def fetch_github_intents(cls, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        intents = []
        queries = [
            "fastapi+OR+paystack+OR+webhook+state:open",
            "sqlite+locked+OR+timeout+state:open",
            "woocommerce+cart+error+state:open"
        ]
        
        for q in queries:
            url = f"https://api.github.com/search/issues?q={q}&sort=created&order=desc&per_page=15"
            try:
                resp = await client.get(url, headers=cls._get_headers())
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    for item in items:
                        title = item.get("title", "")
                        body = item.get("body", "") or ""
                        html_url = item.get("html_url", "")
                        
                        eval_res = evaluate_intent(title, body)
                        if eval_res["matched"]:
                            intents.append({
                                "task_hash": eval_res["task_hash"],
                                "domain": eval_res["domain"],
                                "title": title[:200],
                                "snippet": body[:400] if body else title[:400],
                                "source": html_url,
                                "price": eval_res["price"]
                            })
                await asyncio.sleep(1.0)
            except Exception:
                continue
        return intents

    @classmethod
    async def fetch_stackoverflow_intents(cls, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        intents = []
        tags = ["fastapi", "woocommerce", "shopify", "paystack", "stripe-payments", "docker"]
        tag_str = ";".join(tags)
        url = f"https://api.stackexchange.com/2.3/questions?order=desc&sort=creation&site=stackoverflow&tagged={tag_str}&pagesize=20"
        
        try:
            resp = await client.get(url, headers=cls._get_headers())
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    title = item.get("title", "")
                    link = item.get("link", "")
                    tags_list = item.get("tags", [])
                    body_teaser = f"Tags: {', '.join(tags_list)}. Technical query regarding system behavior and remediation guidance."
                    
                    eval_res = evaluate_intent(title, body_teaser)
                    if eval_res["matched"]:
                        intents.append({
                            "task_hash": eval_res["task_hash"],
                            "domain": eval_res["domain"],
                            "title": title[:200],
                            "snippet": body_teaser[:400],
                            "source": link,
                            "price": eval_res["price"]
                        })
        except Exception:
            pass
        return intents

    @classmethod
    async def fetch_devto_intents(cls, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        intents = []
        tags = ["fastapi", "webdev", "devops", "backend", "python"]
        for tag in tags:
            url = f"https://dev.to/api/articles?tag={tag}&per_page=15"
            try:
                resp = await client.get(url, headers=cls._get_headers())
                if resp.status_code == 200:
                    articles = resp.json()
                    for art in articles:
                        title = art.get("title", "")
                        desc = art.get("description", "") or ""
                        url_art = art.get("url", "")
                        
                        eval_res = evaluate_intent(title, desc)
                        if eval_res["matched"]:
                            intents.append({
                                "task_hash": eval_res["task_hash"],
                                "domain": eval_res["domain"],
                                "title": title[:200],
                                "snippet": desc[:400] if desc else title[:400],
                                "source": url_art,
                                "price": eval_res["price"]
                            })
                await asyncio.sleep(0.5)
            except Exception:
                continue
        return intents

    @classmethod
    async def fetch_rss_community_intents(cls, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        intents = []
        rss_feeds = [
            ("Planet Python", "https://planetpython.org/rss20.xml"),
            ("Dev.to Backend Feed", "https://dev.to/feed/tag/backend")
        ]
        
        for source_name, feed_url in rss_feeds:
            try:
                resp = await client.get(feed_url, headers=cls._get_headers())
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    for item in root.findall(".//item")[:10]:
                        title = item.findtext("title") or ""
                        link = item.findtext("link") or ""
                        desc = item.findtext("description") or ""
                        
                        eval_res = evaluate_intent(title, desc)
                        if eval_res["matched"]:
                            intents.append({
                                "task_hash": eval_res["task_hash"],
                                "domain": eval_res["domain"],
                                "title": title[:200],
                                "snippet": desc[:400] if desc else title[:400],
                                "source": link if link else feed_url,
                                "price": eval_res["price"]
                            })
            except Exception:
                continue
        return intents

    @classmethod
    async def fetch_live_intents(cls) -> List[Dict[str, Any]]:
        all_intents = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # Concurrently sweep Reddit, GitHub, Stack Overflow, Dev.to, and RSS feeds
            results = await asyncio.gather(
                cls.fetch_reddit_intents(client),
                cls.fetch_github_intents(client),
                cls.fetch_stackoverflow_intents(client),
                cls.fetch_devto_intents(client),
                cls.fetch_rss_community_intents(client),
                return_exceptions=True
            )
            
            for res in results:
                if isinstance(res, list):
                    all_intents.extend(res)
                    
        return all_intents
