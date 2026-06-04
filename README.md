# imgfind

Autonomous image discovery and retrieval agent. Searches across multiple sources, ranks candidates using CLIP relevance + aesthetic scoring + perceptual dedup, and presents a ranked shortlist or auto-picks the best match.

## How it works

```
query → router (classify) → [SerpAPI ∥ Brave ∥ gallery-dl ∥ Pexels ∥ Wikimedia ∥ Drive ∥ Crawl4AI]
      → candidate pool → resolution filter → phash dedup → CLIP relevance → aesthetic score
      → z-score blend → vision LLM re-rank (optional) → ranked shortlist
```

**Router:** classifies your query (art keywords → gallery-dl + web, stock keywords → Pexels/Wikimedia, URL → auto-detect source type) and fans out to multiple backends in parallel.

**Ranking pipeline:**
1. Hard filter on minimum resolution
2. Perceptual hash dedup (imagehash, Hamming < 8)
3. CLIP text-image relevance (open_clip ViT-B-32)
4. Aesthetic quality (SigLIP-based aesthetic-predictor-v2-5, 1–10 scale)
5. Z-score normalize + weighted blend (0.5 relevance / 0.3 aesthetic / 0.2 technical)
6. Optional vision LLM re-rank on top-K (Claude Sonnet)

## Install

```bash
git clone https://github.com/shrinav/imgfind.git
cd imgfind
pip install -e .
```

For browser automation (JS-rendered galleries):
```bash
pip install -e ".[browser]"
```

## API Keys

Create a `.env` file in the project root:

```env
# Required — primary search
SERPAPI_API_KEY=your_key_here

# Optional — more sources & features
BRAVE_API_KEY=
PEXELS_API_KEY=
ANTHROPIC_API_KEY=       # for vision LLM re-ranking
GOOGLE_API_KEY=          # for Google Drive folder traversal
```

Only `SERPAPI_API_KEY` is needed to start. Each additional key unlocks more sources.

## Usage

### Search for images

```bash
imgfind search "cyberpunk cityscape" --n 10
imgfind search "serene japanese garden" --license cc --n 5
imgfind search "anime girl neon" --sources web,danbooru
```

### Extract images from a URL

```bash
imgfind from-url "https://www.artstation.com/artwork/xyz"
imgfind from-url "https://drive.google.com/drive/folders/abc123"
```

### Visual grid picker

```bash
imgfind search "mountain landscape" --grid
```

Opens a local web UI with thumbnails, score badges, and click-to-pick. Press 1–9 to quick-select.

### Autonomous mode

```bash
imgfind auto "product photo of headphones" --out assets/ --format webp
```

Searches, ranks, auto-picks if confidence is high enough, downloads + optimizes, writes a sidecar JSON with source/license/attribution.

### Download a specific candidate

```bash
imgfind fetch abc123def456 --out assets/ --width 1200 --format webp
```

### Rank local images

```bash
imgfind rank ./my-images/ --query "professional headshot"
```

### Tune ranking weights

```bash
imgfind tune
```

Fits blend weights from your pick history (recorded via grid UI).

## Flags

| Flag | Description |
|------|-------------|
| `--fast` | Skip ML ranking, resolution filter only |
| `--no-vision` | Skip vision LLM re-ranking |
| `--grid` | Open grid UI instead of terminal output |
| `--json` | Output as JSON |
| `--license cc\|royalty_free\|public_domain` | Prefer permissive sources |
| `--sources web,pexels,wikimedia,...` | Explicit source selection |
| `--min-res 1024` | Minimum resolution (long edge px) |
| `-v` | Verbose logging |

## Sources

| Source | Type | License tracking |
|--------|------|-----------------|
| SerpAPI | Google Images | auto |
| Brave Search | Independent index | auto |
| gallery-dl | 170+ art sites (Pixiv, Danbooru, ArtStation, DeviantArt, Reddit, Twitter...) | flags copyrighted |
| Pexels | Stock photos | Pexels license + attribution |
| Wikimedia Commons | CC/public domain with per-file metadata | CC-BY/CC0/PD |
| Google Drive | Folder traversal via API | unknown |
| Crawl4AI | Generic HTML extraction | unknown |
| browser-use | JS-rendered/login-gated (escalation) | unknown |

## Architecture

```
imgfind/
├── cli.py              # Typer CLI
├── engine.py           # Orchestrator: router → sources → ranking → DB
├── router.py           # Query classification → strategy dispatch
├── models.py           # Candidate, SearchResult, LicenseType
├── config.py           # Config from env vars + defaults
├── feedback.py         # Preference-based weight tuning
├── sources/            # One module per search backend
├── ranking/
│   ├── image_cache.py  # Download-once cache shared across scorers
│   ├── clip_scorer.py  # CLIP text-image relevance
│   ├── aesthetic.py    # SigLIP aesthetic predictor (1-10)
│   ├── technical.py    # MUSIQ technical IQA (optional)
│   ├── dedup.py        # Perceptual hash deduplication
│   ├── vision_rerank.py # Claude vision re-ranking (top-K)
│   ├── blend.py        # Z-score / RRF score blending
│   └── pipeline.py     # Orchestrates the ranking stages
├── storage/
│   ├── db.py           # SQLite candidate cache + preferences
│   └── assets.py       # Download, optimize, sidecar JSON, manifest
└── ui/
    ├── server.py       # FastAPI grid UI
    ├── terminal.py     # Terminal shortlist printer
    └── static/         # Dark-theme grid with score badges
```

## Cost

| Component | Cost per search |
|-----------|----------------|
| SerpAPI | Free (100/month) |
| Brave | ~$0.005 |
| CLIP + aesthetic | Free (local) |
| Vision re-rank | ~$0.03–0.10 (opt-in) |

## License

MIT
