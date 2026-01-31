"""Web search plugin example."""
from __future__ import annotations

import httpx

from gateway.domain.models import ToolPermission, ToolSpec
from gateway.plugins.registry import PluginRegistry


async def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web for information.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        Search results with titles and URLs
    """
    # This is a mock implementation
    # In production, integrate with actual search APIs (Google, Bing, etc.)
    
    results = [
        {
            "title": f"Result {i+1} for: {query}",
            "url": f"https://example.com/result/{i+1}",
            "snippet": f"This is a search result snippet for query: {query}",
        }
        for i in range(max_results)
    ]
    
    return {
        "query": query,
        "total_results": len(results),
        "results": results,
    }


async def fetch_url(url: str) -> dict:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        Page title and content snippet
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # In production, parse HTML properly
            content = response.text[:1000]
            
            return {
                "url": url,
                "status": response.status_code,
                "content_preview": content,
                "content_length": len(response.text),
            }
    except Exception as e:
        return {
            "url": url,
            "error": str(e),
        }


def register(registry: PluginRegistry) -> None:
    """Register web search plugin."""
    
    # Register web search tool
    registry.register_tool(
        ToolSpec(
            name="web.search",
            description="Search the web for information on any topic",
            permission=ToolPermission.read,
            func=web_search,
            parameters={
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-10)",
                    "default": 5,
                },
            },
        )
    )
    
    # Register URL fetch tool
    registry.register_tool(
        ToolSpec(
            name="web.fetch",
            description="Fetch content from a specific URL",
            permission=ToolPermission.read,
            func=fetch_url,
            parameters={
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                },
            },
        )
    )
    
    print("✅ Web search plugin loaded successfully")
