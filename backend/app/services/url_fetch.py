import ipaddress, socket
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

class UnsafeURL(ValueError): pass

def _public_host(host: str) -> bool:
    try:
        return all(not (ipaddress.ip_address(x[4][0]).is_private or ipaddress.ip_address(x[4][0]).is_loopback or ipaddress.ip_address(x[4][0]).is_link_local) for x in socket.getaddrinfo(host, None))
    except (socket.gaierror, ValueError): return False

async def fetch_article(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not _public_host(parsed.hostname):
        raise UnsafeURL("Only public HTTP(S) article URLs are allowed")
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, headers={"User-Agent": "SatyaLens/0.1"}) as client:
        current = url
        for _ in range(4):
            r = await client.get(current)
            if r.is_redirect:
                target = str(r.next_request.url)
                p = urlparse(target)
                if not p.hostname or not _public_host(p.hostname): raise UnsafeURL("Redirect resolved to a non-public host")
                current = target; continue
            r.raise_for_status()
            if "text/html" not in r.headers.get("content-type", ""): raise ValueError("URL did not return HTML")
            if len(r.content) > 2_000_000: raise ValueError("Article exceeds 2 MB limit")
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]): tag.decompose()
            text = " ".join(soup.get_text(" ").split())
            return text[:50_000]
        raise UnsafeURL("Too many redirects")
