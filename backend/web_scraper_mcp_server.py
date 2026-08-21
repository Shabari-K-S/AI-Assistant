#!/usr/bin/env python3
"""Custom Web Scraper and Content Reader MCP Server for S.A.R.A.

Fetches and extracts clean, readable text, articles, and hyperlinks directly from websites
without requiring commercial search or scraping API keys.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Athena Assistant)"

TOOLS = [
    {
        "name": "scrape_web_page",
        "description": "Fetch, scrape, and extract clean readable text, headers, and article content directly from any website URL with ZERO API keys.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full HTTP/HTTPS URL of the website or article to scrape and read.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of content characters to extract (default: 4000).",
                    "default": 4000,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "extract_page_links",
        "description": "Extract all outbound hyperlinks, navigation targets, and page titles from a web page URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to extract hyperlinks from.",
                },
                "max_links": {
                    "type": "integer",
                    "description": "Maximum number of links to return (default: 15).",
                    "default": 15,
                },
            },
            "required": ["url"],
        },
    },
]


def _clean_scraped_text(raw_html: str) -> str:
    # 1. Remove script, style, SVG, and nav tags
    clean = re.sub(r"<(script|style|svg|noscript|header|footer|nav)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # 2. Convert paragraph and heading tags to newlines
    clean = re.sub(r"</?(p|div|h[1-6]|li|tr|br)[^>]*>", "\n", clean, flags=re.IGNORECASE)
    # 3. Strip remaining tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # 4. Unescape HTML entities
    clean = html.unescape(clean)
    # 5. Normalize whitespace while preserving structural paragraphs
    lines = [line.strip() for line in clean.split("\n") if line.strip()]
    return "\n\n".join(lines)


def fetch_url_content(url: str, timeout: float = 10.0) -> tuple[str, str]:
    """Fetch URL and return (title, html_body)."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        raw_bytes = response.read()
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        body = raw_bytes.decode(charset, errors="replace")

    title_match = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    title = html.unescape(title_match.group(1)).strip() if title_match else url
    return title, body


def handle_scrape_web_page(args: dict[str, Any]) -> str:
    url = str(args.get("url", "")).strip()
    if not url:
        return "error: url parameter is required"
    max_chars = min(15000, max(500, int(args.get("max_chars", 4000))))

    try:
        title, body = fetch_url_content(url)
        clean_text = _clean_scraped_text(body)
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars] + "\n\n[... content truncated for length ...]"

        out = [
            f"📄 Scraped Content from: {url}",
            f"📌 Title: {title}",
            "━" * 50,
            clean_text or "No readable text content found.",
            "━" * 50,
        ]
        return "\n".join(out)
    except Exception as exc:
        return f"error: failed to scrape URL '{url}': {exc}"


def handle_extract_page_links(args: dict[str, Any]) -> str:
    url = str(args.get("url", "")).strip()
    if not url:
        return "error: url parameter is required"
    max_links = min(50, max(1, int(args.get("max_links", 15))))

    try:
        title, body = fetch_url_content(url)
        raw_links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.IGNORECASE | re.DOTALL)

        links_out: list[tuple[str, str]] = []
        seen = set()

        for href, text in raw_links:
            clean_t = _clean_scraped_text(text).strip()
            absolute_url = urllib.parse.urljoin(url, href.strip())

            if absolute_url.startswith("http") and absolute_url not in seen:
                seen.add(absolute_url)
                links_out.append((clean_t or "Link", absolute_url))
                if len(links_out) >= max_links:
                    break

        if not links_out:
            return f"No links found on {url}"

        lines = [f"🔗 Extracted Links from: {title} ({url})\n"]
        for i, (label, link) in enumerate(links_out, 1):
            lines.append(f"{i}. {label} -> {link}")
        return "\n".join(lines)
    except Exception as exc:
        return f"error: failed to extract links from '{url}': {exc}"


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "scrape_web_page":
        out = handle_scrape_web_page(args)
    elif name == "extract_page_links":
        out = handle_extract_page_links(args)
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
                        "name": "web-scraper-mcp-server",
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
