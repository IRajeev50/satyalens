"""Open-web / primary-source search (labeled search seam, now implemented).

Provider-agnostic: Tavily or Brave. Like the fact-check retriever, this degrades
honestly - with no key configured it returns zero results and a warning, and the
pipeline abstains rather than inventing evidence. Returned snippets are UNTRUSTED
DATA; the reasoning layer sanitizes and injection-scans each one before it reaches
the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

TAVILY_URL = "https://api.tavily.com/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


@dataclass
class WebResult:
    items: list[dict] = field(default_factory=list)
    warning: str | None = None


def _domain(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


class WebSearchClient:
    """Thin adapter over a web search API. ``provider`` selects the backend."""

    def __init__(self, api_key: str | None, provider: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None, max_results: int = 5):
        self.api_key = api_key
        # Infer provider from an explicit setting, else default to tavily when a key exists.
        self.provider = (provider or ("tavily" if api_key else None))
        self.transport = transport
        self.max_results = max_results

    async def search(self, query: str) -> WebResult:
        if not self.api_key or not self.provider:
            return WebResult(warning="No web-search key configured; verification proceeds without open-web evidence.")
        try:
            async with httpx.AsyncClient(timeout=12, transport=self.transport) as client:
                if self.provider == "brave":
                    return self._parse_brave(await self._brave(client, query))
                return self._parse_tavily(await self._tavily(client, query))
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return WebResult(warning=f"Web search unavailable ({type(exc).__name__}); continued without open-web evidence.")

    async def _tavily(self, client: httpx.AsyncClient, query: str) -> dict:
        r = await client.post(TAVILY_URL, json={
            "api_key": self.api_key, "query": query,
            "max_results": self.max_results, "search_depth": "advanced",
        })
        r.raise_for_status()
        return r.json()

    async def _brave(self, client: httpx.AsyncClient, query: str) -> dict:
        r = await client.get(BRAVE_URL, params={"q": query, "count": self.max_results},
                             headers={"X-Subscription-Token": self.api_key,
                                      "Accept": "application/json"})
        r.raise_for_status()
        return r.json()

    def _parse_tavily(self, payload: dict) -> WebResult:
        items = []
        for row in (payload.get("results") or [])[: self.max_results]:
            url = row.get("url") or ""
            if not url:
                continue
            items.append({
                "source_url": url,
                "source_title": row.get("title") or url,
                "publisher": _domain(url),
                "quote": (row.get("content") or "").strip(),
                "relation": "related",
                "rating": None,
                "raw": {"score": row.get("score"), "source_type": "web_search",
                        "published_date": row.get("published_date")},
            })
        return WebResult(items=[x for x in items if x["quote"]])

    def _parse_brave(self, payload: dict) -> WebResult:
        items = []
        for row in ((payload.get("web") or {}).get("results") or [])[: self.max_results]:
            url = row.get("url") or ""
            if not url:
                continue
            items.append({
                "source_url": url,
                "source_title": row.get("title") or url,
                "publisher": _domain(url),
                "quote": (row.get("description") or "").strip(),
                "relation": "related",
                "rating": None,
                "raw": {"source_type": "web_search", "age": row.get("age")},
            })
        return WebResult(items=[x for x in items if x["quote"]])


def build_client(settings) -> WebSearchClient | None:
    """Return a configured client, or None when no web-search key is set."""
    if not settings.search_api_key:
        return None
    return WebSearchClient(settings.search_api_key, settings.search_provider)
