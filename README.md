# imgfind

**Image search for AI agents that actually see what they recommend.**

AI assistants search for images blind. They read titles and URLs but never look at the actual pictures. So they recommend paywalled images, wrong backgrounds, pixel art when you wanted illustration, dead links. You only find out after downloading.

imgfind fixes this. Search multiple backends, composite the top candidates into a single labeled grid, and let your AI agent visually compare and rank them. The same way you'd scan a contact sheet.

## How it works

```
Your agent crafts search queries (multiple angles per backend)
    -> imgfind searches Google, Brave, Danbooru, Pexels, Wikimedia in parallel
    -> Downloads top candidates, composites into a labeled grid image
    -> Your agent views the grid, visually ranks against your actual needs
    -> Presents top picks with URLs and explanations
```

The AI agent is both the query planner and the visual ranker. No separate LLM API calls. No embeddings. Your agent just looks at the grid.

## Why a grid?

Based on the [SQUARE paper](https://arxiv.org/abs/2503.15573). Comparing all candidates side-by-side in one image beats scoring them one at a time. One vision pass over a 2x5 grid is faster, cheaper, and more accurate than 10 separate image evaluations.

- 384px thumbnails with LANCZOS resampling
- Gray background (128,128,128) so you can tell white, black, and transparent backgrounds apart
- Labeled A-J for easy reference

## Multi-query branching

One search query isn't enough. imgfind accepts multiple queries per backend. They all run in parallel, results get pooled and deduped into one grid:

```bash
python -m imgfind.cc_search \
  --query "Gojo Satoru" \
  --google "Gojo Satoru digital art illustration high quality" \
           "Gojo Satoru transparent background PNG render" \
  --danbooru "gojo_satoru solo highres -lowres"
```

Different angles surface different results. The grid reranker picks the best from the combined pool.

## Claude Code integration

imgfind was built to work with [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Add instructions to your `CLAUDE.md` and Claude will use imgfind whenever you ask for an image:

```markdown
## imgfind
When the user asks to find an image, use imgfind. Two steps:

### Step 1: Search
Craft search queries based on the conversation context.
\```bash
cd <path-to-imgfind> && PYTHONIOENCODING=utf-8 python -m imgfind.cc_search \
  --query "base query" --google "angle 1" "angle 2" --brave "angle 3"
\```
Branch out with multiple search angles per backend.

### Step 2: View + Rank
Read the grid image at `<path-to-imgfind>/.imgfind_output/grid.jpg`.
Rank candidates against the user's actual needs. Present top picks with URLs.
```

Claude Code reads the grid image directly. It sees the actual candidates and can judge backgrounds, art style, quality, and whether the image actually fits what you need.

## Setup

```bash
git clone https://github.com/lokashrinav/imgfind.git
cd imgfind
pip install -e .
```

Create a `.env` file:

```env
SERPAPI_API_KEY=your_key      # Required
BRAVE_API_KEY=                # Optional, independent search index
PEXELS_API_KEY=               # Optional, stock photos
```

Only `SERPAPI_API_KEY` is needed to start. Each additional key adds more backends.

## Query syntax per backend

| Backend | Syntax | Example |
|---------|--------|---------|
| Google/Brave | Natural language, `-term` to exclude | `"Sans fan art -pixel_art -sprite"` |
| Danbooru | Underscored tags, `-tag` to exclude | `"sans_(undertale) solo highres -lowres"` |
| Pexels/Wikimedia | Simple keywords only | `"mountain landscape sunset"` |

## Backends

| Source | What it searches | Best for |
|--------|-----------------|----------|
| SerpAPI | Google Images | General search, broad coverage |
| Brave | Independent index | Different results than Google |
| Danbooru | Tagged art database | Anime, fan art, illustrations |
| Pexels | Stock photos | Clean commercial-use photos |
| Wikimedia | CC/public domain | Free-license images |

## Why this exists

AI web search recommends images it has never seen. In testing, 3 out of 6 AI-recommended images for "Gojo Satoru" were broken. One was paywalled, one was a dead link, one had the wrong background color. imgfind catches all of these because the AI actually looks at the candidates before recommending them.

## License

MIT
