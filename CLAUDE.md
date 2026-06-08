# imgfind — Image Search Tool

When the user asks you to find, search for, or get an image, use imgfind. Do NOT use web search. Two steps:

## Step 1: Search

Think about what the user actually needs based on the full conversation, then craft the best search query. Translate use cases into concrete visual attributes:
- "YouTube thumbnail" → clean/white background, high contrast, eye-catching, portrait framing
- "Discord PFP" → square-friendly, upper body/bust, simple background
- "wallpaper" → landscape, high resolution, detailed
- "meme template" → clean background, expressive pose, transparent PNG
- "portfolio" / "website" → transparent PNG or clean background, high quality, professional presentation
- "too dark" / "not what I wanted" → refine query based on what failed

```bash
PYTHONIOENCODING=utf-8 python -m imgfind.cc_search --query "base query" --duckduckgo "angle 1" "angle 2" --google "angle 3" --danbooru "tag_query"
```

**Branch out with multiple search angles.** Each backend accepts multiple queries — all run in parallel and results are pooled into one grid. Think about different ways to find what the user needs:
- Quality angle: `"Sans Undertale digital art illustration high quality"`
- Format angle: `"Sans Undertale transparent background PNG render"`
- Style angle: `"Sans Undertale fan art portrait clean"`

### Available backends
- **`--duckduckgo`**: Free, no API key. Use as default.
- **`--google`**: SerpAPI (needs SERPAPI_API_KEY). Best coverage.
- **`--brave`**: Brave Search (needs BRAVE_API_KEY). Independent index.
- **`--danbooru`**: Tag-based art search. Use underscored tags, `-tag` to exclude (e.g., `"sans_(undertale) solo highres -pixel_art"`). Has autocomplete API — use `expand_query()` from `imgfind.sources.gallery` to convert natural language to tags.
- **`--pexels`/`--wikimedia`**: Stock/free photos. Skip for fictional characters.

### Query syntax
- **Google/Brave**: use `-term` to exclude (e.g., `"fan art -pixel_art -sprite"`). Never use natural language negation ("not pixel art") — search engines ignore it.
- **Danbooru**: underscored tags with `name_(series)` format for characters. `-tag` to exclude.
- **Pexels/Wikimedia**: simple keywords only, no negation.

## Step 2: View + Rank

Read the grid image at `.imgfind_output/grid.jpg`. Visually rank candidates against the **user's actual use case**, not just query relevance. Consider whether each image would actually work for their stated purpose (e.g., a dark moody image might be great art but wrong for a portfolio page). When good art has the wrong background, suggest the user can remove/swap the background — don't throw away quality results just to re-search for worse art with the "right" background.

Present the top 2-3 picks with URLs and explanations. If results are bad, refine the query and search again.

Ask the user if they want to see the grid themselves. If yes, open it with the system default viewer.

## Python API

For programmatic use (background agents, scripts):

```python
from imgfind.search import search

result = await search(
    "Gojo Satoru",
    google=["Gojo digital art", "Gojo transparent PNG"],
    duckduckgo=["Gojo Satoru fan art"],
)
grid_path = result["grid_image"]
candidates = result["candidate_map"]
```
