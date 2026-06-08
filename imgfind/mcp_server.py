"""MCP server exposing imgfind image search as a tool.

Run:
    python -m imgfind.mcp_server
"""
from __future__ import annotations

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

mcp = FastMCP("agentimagesearch")


@mcp.tool(
    name="search_images",
    description="Search for images across multiple backends and return a ranked grid of candidates",
)
async def search_images(
    query: str,
    google: list[str] | None = None,
    duckduckgo: list[str] | None = None,
    brave: list[str] | None = None,
    danbooru: list[str] | None = None,
    pexels: list[str] | None = None,
    wikimedia: list[str] | None = None,
    n: int = 10,
) -> list[TextContent | ImageContent]:
    """Search for images across multiple backends and return a ranked grid of candidates.

    Args:
        query: The search query.
        google: Google/SerpAPI search queries.
        duckduckgo: DuckDuckGo search queries (free, no API key).
        brave: Brave search queries.
        danbooru: Danbooru tag queries.
        pexels: Pexels search queries.
        wikimedia: Wikimedia search queries.
        n: Number of candidates (default 10).
    """
    from imgfind.search import search

    result = await search(
        query,
        google=google,
        duckduckgo=duckduckgo,
        brave=brave,
        danbooru=danbooru,
        pexels=pexels,
        wikimedia=wikimedia,
        n=n,
    )

    if result.get("status") == "error":
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": result.get("message", "Search failed"),
                        "errors": result.get("errors", []),
                    },
                    indent=2,
                ),
            )
        ]

    candidate_map = result.get("candidate_map", {})
    grid_path = result.get("grid_image", "")
    total_found = result.get("total_found", 0)
    errors = result.get("errors", [])

    text_payload = json.dumps(
        {
            "status": "ready",
            "grid_image": grid_path,
            "total_found": total_found,
            "candidate_map": candidate_map,
            "errors": errors,
        },
        indent=2,
    )

    contents: list[TextContent | ImageContent] = [
        TextContent(type="text", text=text_payload),
    ]

    grid_bytes = result.get("grid_bytes")
    if grid_bytes:
        contents.append(
            ImageContent(
                type="image",
                data=base64.b64encode(grid_bytes).decode("ascii"),
                mimeType="image/jpeg",
            )
        )

    return contents


if __name__ == "__main__":
    mcp.run()
