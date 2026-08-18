#!/usr/bin/env python3
"""DuckDuckGo Search MCP Server for S.A.R.A.

Provides free, open web search and news search over standard stdio JSON-RPC 2.0.
Requires ZERO API keys and no third-party account registration.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

TOOLS = [
    {
        "name": "duckduckgo_search",
        "description": "Perform a real-time web search via DuckDuckGo to find current information, websites, facts, documentation, and answers with ZERO API keys required.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search keywords or question to search the web for.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default: 5, max: 10).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "duckduckgo_news",
        "description": "Search latest news articles, headlines, and current events via DuckDuckGo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topic, person, or event to search news for.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of news results to return (default: 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]


def _clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities into clean plain text."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_wikipedia_results(query: str, max_results: int = 4) -> list[dict[str, str]]:
    """Fetch encyclopedic articles from Wikipedia Search API."""
    try:
        w_q = urllib.parse.quote(query)
        w_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={w_q}&utf8=&format=json"
        req = urllib.request.Request(w_url, headers={"User-Agent": "SARA-Research-Intelligence/2.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
            search_items = data.get("query", {}).get("search", [])
            out = []
            for item in search_items[:max_results]:
                title = item.get("title", "")
                snippet = _clean_html(item.get("snippet", ""))
                article_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                out.append({
                    "title": f"{title} (Wikipedia Encyclopedia)",
                    "url": article_url,
                    "snippet": snippet or "Wikipedia article entry.",
                })
            return out
    except Exception as exc:
        log_msg = str(exc)
        return []


def _fetch_arxiv_results(query: str, max_results: int = 4) -> list[dict[str, str]]:
    """Fetch published academic papers from the ArXiv API."""
    try:
        import xml.etree.ElementTree as ET
        clean_q = re.sub(r"[^\w\s]", " ", query).strip()
        a_q = urllib.parse.quote(clean_q)
        a_url = f"http://export.arxiv.org/api/query?search_query=all:{a_q}&start=0&max_results={max_results}"
        req = urllib.request.Request(a_url, headers={"User-Agent": "SARA-Research-Intelligence/2.0"})
        with urllib.request.urlopen(req, timeout=7) as response:
            root = ET.fromstring(response.read())
            entries = root.findall("{http://www.w3.org/2005/Atom}entry")
            out = []
            for entry in entries:
                title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                id_elem = entry.find("{http://www.w3.org/2005/Atom}id")
                summary_elem = entry.find("{http://www.w3.org/2005/Atom}summary")

                t = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "ArXiv Paper"
                link = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                s = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""

                if link:
                    out.append({
                        "title": f"{t} (ArXiv Research Paper)",
                        "url": link,
                        "snippet": s[:350] if s else "ArXiv scientific preprint.",
                    })
            return out
    except Exception:
        return []


def perform_ddg_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Perform multi-source web and academic search via DuckDuckGo, ArXiv, and Wikipedia."""
    results: list[dict[str, str]] = []
    seen_urls = set()

    # 1. Attempt DuckDuckGo HTML endpoint
    try:
        encoded_query = urllib.parse.urlencode({"q": query, "b": ""})
        url = f"https://html.duckduckgo.com/html/?{encoded_query}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            content = response.read().decode("utf-8", errors="replace")

        blocks = re.findall(r'<div[^>]*class="[^"]*result\s+results_links[^"]*"[^>]*>(.*?)</div>\s*</div>', content, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'<div[^>]*class="[^"]*result__body[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'<div[^>]*class="[^"]*web-result[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL)

        for block in blocks:
            title_match = re.search(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL)
            link_match = re.search(r'<a[^>]*class="[^"]*(?:result__a|result__url)[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not link_match:
                link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)

            title = ""
            raw_url = ""
            snippet = ""

            if link_match:
                raw_url = link_match.group(1)
                title = _clean_html(link_match.group(2))

            if title_match:
                snippet = _clean_html(title_match.group(1))

            if not snippet:
                snip_div = re.search(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)<', block, re.DOTALL)
                if snip_div:
                    snippet = _clean_html(snip_div.group(1))

            # Decode redirect link
            if "/l/?" in raw_url and "uddg=" in raw_url:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                if "uddg" in parsed:
                    raw_url = parsed["uddg"][0]
            elif raw_url.startswith("//"):
                raw_url = "https:" + raw_url

            if raw_url and raw_url.startswith("http") and not raw_url.startswith("https://duckduckgo.com/"):
                if raw_url not in seen_urls:
                    seen_urls.add(raw_url)
                    results.append({
                        "title": title or raw_url,
                        "url": raw_url,
                        "snippet": snippet or "No snippet available",
                    })

            if len(results) >= max_results:
                break
    except Exception:
        pass

    # 2. Supplement with ArXiv Scholarly Papers (especially for technical/research topics)
    if len(results) < max_results:
        arxiv_items = _fetch_arxiv_results(query, max_results=max(3, max_results - len(results)))
        for item in arxiv_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                results.append(item)

    # 3. Supplement with Wikipedia Technical & Conceptual Articles
    if len(results) < max_results:
        wiki_items = _fetch_wikipedia_results(query, max_results=max(3, max_results - len(results)))
        for item in wiki_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                results.append(item)

    return results[:max_results]


def perform_ddg_news(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search news using DuckDuckGo search queries."""
    news_q = f"{query} news" if "news" not in query.lower() else query
    return perform_ddg_search(news_q, max_results=max_results)


def handle_duckduckgo_search(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return "error: query parameter is required"
    max_res = min(15, max(1, int(args.get("max_results", 5))))

    results = perform_ddg_search(query, max_results=max_res)
    if not results:
        return f"No DuckDuckGo results found for query: '{query}'"

    lines = [f"🔍 DuckDuckGo Web Results for: '{query}'\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   URL: {r['url']}")
        lines.append(f"   Snippet: {r['snippet']}\n")
    return "\n".join(lines).strip()


def handle_duckduckgo_news(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return "error: query parameter is required"
    max_res = min(10, max(1, int(args.get("max_results", 5))))

    news_query = f"{query} news"
    results = perform_ddg_search(news_query, max_results=max_res)
    if not results:
        return f"No news results found for: '{query}'"

    lines = [f"📰 DuckDuckGo News Results for: '{query}'\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   URL: {r['url']}")
        lines.append(f"   Summary: {r['snippet']}\n")
    return "\n".join(lines).strip()


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "duckduckgo_search":
        out = handle_duckduckgo_search(args)
    elif name == "duckduckgo_news":
        out = handle_duckduckgo_news(args)
    else:
        out = f"error: unknown tool '{name}'"

    return {
        "content": [
            {
                "type": "text",
                "text": out,
            }
        ]
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "duckduckgo-mcp-server",
                        "version": "1.0.0",
                    },
                },
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            }
        elif method == "tools/call":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": handle_call_tool(params),
            }
        elif req_id is not None:
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
            }
        else:
            continue

        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
