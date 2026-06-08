# agentimagesearch

Image search for AI agents that actually see what they recommend.

AI assistants search for images blind. They read titles and URLs but never look at the actual pictures. So they recommend paywalled images, wrong backgrounds, pixel art when you wanted illustration, dead links. You only find out after downloading.

agentimagesearch fixes this. Search multiple backends, composite the top candidates into a single labeled grid, and let your AI agent visually compare and rank them. The same way you'd scan a contact sheet.

## How it works

```
Your agent crafts search queries (multiple angles per backend)
    -> searches Google, Brave, DuckDuckGo, Danbooru, Pexels, Wikimedia in parallel
    -> Downloads top candidates, composites into a labeled grid image
    -> Your agent views the grid, visually ranks against your actual needs
    -> Presents top picks with URLs and explanations
```

The AI agent is both the query planner and the visual ranker. No separate LLM API calls. No embeddings. Your agent just looks at the grid.

## Setup

```bash
git clone https://github.com/lokashrinav/agentimagesearch.git
cd agentimagesearch
pip install -e ".[all]"
```

That's it. The repo includes a `CLAUDE.md` that Claude Code picks up automatically. Clone it, run Claude Code in the directory, and ask for an image. It just works.

No API keys required to start. DuckDuckGo search is free and built in. Add keys for more backends:

```env
# .env (all optional)
SERPAPI_API_KEY=your_key      # Google Images via SerpAPI
BRAVE_API_KEY=your_key        # Brave Search
PEXELS_API_KEY=your_key       # Pexels stock photos
```

## Why a grid?

Based on the [SQUARE paper](https://arxiv.org/abs/2503.15573). Comparing all candidates side-by-side in one image beats scoring them one at a time. One vision pass over a 2x5 grid is faster, cheaper, and more accurate than 10 separate image evaluations.

- 384px thumbnails with LANCZOS resampling
- Gray background so you can tell white, black, and transparent backgrounds apart
- Labeled A-J for easy reference

## Multi-query branching

One search query isn't enough. Each backend accepts multiple queries. They all run in parallel, results get pooled and deduped into one grid:

```bash
python -m imgfind.cc_search \
  --query "Gojo Satoru" \
  --duckduckgo "Gojo Satoru fan art illustration" \
  --google "Gojo Satoru digital art high quality" \
           "Gojo Satoru transparent background PNG render" \
  --danbooru "gojo_satoru solo highres -lowres"
```

Different angles surface different results. The grid shows the best from the combined pool.

## Backends

| Source | API key needed? | Best for |
|--------|----------------|----------|
| DuckDuckGo | No | General search, zero setup |
| SerpAPI | Yes | Google Images, best coverage |
| Brave | Yes | Independent index |
| Danbooru | No | Anime, fan art, illustrations |
| Pexels | Yes | Stock photos |
| Wikimedia | No | CC/public domain images |

Danbooru has a built-in tag autocomplete API. Natural language like "Sans Undertale transparent background" gets converted to proper tags like `sans_(undertale) transparent_background` automatically.

## Hosted API

A free hosted API is live at `https://agentimagesearch.onrender.com`. No setup, no keys, just POST:

```bash
curl -X POST https://agentimagesearch.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "cute cat", "duckduckgo": ["cute cat photo", "kitten portrait"]}'
```

Returns candidate URLs, metadata, and a grid image you can fetch at `/grid/{search_id}`.

| Endpoint | Description |
|----------|-------------|
| `POST /search` | Run a search. Pass `query` and optional backend-specific query lists |
| `GET /grid/{search_id}` | Get the grid image for a specific search |
| `GET /grid` | Get the most recent grid image |

The API supports all the same backends as the CLI. DuckDuckGo works out of the box. To use Google/Brave/Pexels, set the corresponding API key env vars on your own deployment.

## MCP server

For AI agents that support MCP (Model Context Protocol), agentimagesearch exposes a `search_images` tool that returns both candidate metadata and the grid image inline:

```bash
pip install -e ".[mcp]"
python -m imgfind.mcp_server
```

Add it to your MCP config and your agent gets image search with visual verification built in.

## AI agent integration

agentimagesearch ships with a `CLAUDE.md` that tells Claude Code how to use it. Clone the repo and Claude Code knows:
- How to craft multi-angle search queries
- Which backends to hit for different types of images
- How to read and rank the grid results
- When to suggest background removal vs re-searching

For other AI agents, use the Python API:

```python
from imgfind.search import search

result = await search(
    "Gojo Satoru",
    duckduckgo=["Gojo fan art illustration"],
    google=["Gojo transparent PNG render"],
)

grid_path = result["grid_image"]    # path to the grid image
candidates = result["candidate_map"] # labeled candidates with URLs
```

## Why this exists

AI web search recommends images it has never seen. In testing, 3 out of 6 AI-recommended images for "Gojo Satoru" were broken. One was paywalled, one was a dead link, one had the wrong background color. agentimagesearch catches all of these because the AI actually looks at the candidates before recommending them.

## License

MIT
