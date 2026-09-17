from dataclasses import dataclass, field
import httpx

API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
@dataclass
class RetrievalResult:
    items: list[dict] = field(default_factory=list)
    warning: str | None = None

class FactCheckRetriever:
    def __init__(self, api_key: str | None, transport: httpx.AsyncBaseTransport | None = None):
        self.api_key, self.transport = api_key, transport
    async def search(self, query: str, language_code: str = "en") -> RetrievalResult:
        if not self.api_key:
            return RetrievalResult(warning="Google Fact Check API key is not configured; assessment is based on no external evidence.")
        try:
            async with httpx.AsyncClient(timeout=8, transport=self.transport) as client:
                response = await client.get(API_URL, params={"query": query, "key": self.api_key, "languageCode": language_code if language_code in {"en","hi"} else "en"})
                response.raise_for_status()
                claims = response.json().get("claims", [])
                items = []
                for claim in claims[:5]:
                    for review in claim.get("claimReview", [])[:2]:
                        items.append({
                            "source_url": review.get("url", ""),
                            "source_title": review.get("title") or claim.get("text") or "Published fact check",
                            "publisher": (review.get("publisher") or {}).get("name"),
                            "quote": claim.get("text") or query,
                            "rating": review.get("textualRating"),
                            "relation": "related",
                            "raw": {"source_type": "fact_check", "claimant": claim.get("claimant"), "claim_date": claim.get("claimDate")},
                        })
                return RetrievalResult(items=[x for x in items if x["source_url"]])
        except (httpx.HTTPError, ValueError) as exc:
            return RetrievalResult(warning=f"Fact-check retrieval unavailable ({type(exc).__name__}); continued without external evidence.")
