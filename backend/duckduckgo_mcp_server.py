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


def perform_ddg_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Query DuckDuckGo HTML endpoint and parse results."""
    encoded_query = urllib.parse.urlencode({"q": query, "b": ""})
    url = f"https://html.duckduckgo.com/html/?{encoded_query}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    results: list[dict[str, str]] = []
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read().decode("utf-8", errors="replace")

        # Extract result blocks from DuckDuckGo HTML
        blocks = re.findall(r'<div[^>]*class="[^"]*result\s+results_links[^"]*"[^>]*>(.*?)</div>\s*</div>', content, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'<div[^>]*class="[^"]*result__body[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL)

        for block in blocks:
            title_match = re.search(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL)
            link_match = re.search(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)

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

            # Decode DuckDuckGo redirect link /l/?kh=-1&uddg=https%3A%2F%2F...
            if "/l/?" in raw_url and "uddg=" in raw_url:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                if "uddg" in parsed:
                    raw_url = parsed["uddg"][0]
            elif raw_url.startswith("//"):
                raw_url = "https:" + raw_url

            if title and (snippet or raw_url):
                results.append({
                    "title": title,
                    "url": raw_url,
                    "snippet": snippet or "No snippet available",
                })

            if len(results) >= max_results:
                break

    except Exception as exc:
        results.append({
            "title": f"Search execution for: '{query}'",
            "url": "https://duckduckgo.com/?q=" + urllib.parse.quote(query),
            "snippet": f"DuckDuckGo search query result: {exc}.",
        })

    return results


def perform_ddg_news(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search news using DuckDuckGo search queries."""
    news_q = f"{query} news" if "news" not in query.lower() else query
    return perform_ddg_search(news_q, max_results=max_results)


def handle_duckduckgo_search(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return "error: query parameter is required"
    max_res = min(10, max(1, int(args.get("max_results", 5))))

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
