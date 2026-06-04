from __future__ import annotations

import json
import sqlite3

from imgfind.config import config
from imgfind.models import Candidate, LicenseType


class Database:
    def __init__(self, path: str | None = None):
        self.path = path or str(config.db_path)
        config.ensure_dirs()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                source TEXT,
                source_page TEXT,
                title TEXT,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                format TEXT,
                license TEXT,
                attribution TEXT,
                metadata TEXT,
                relevance_score REAL DEFAULT 0,
                aesthetic_score REAL DEFAULT 0,
                technical_score REAL DEFAULT 0,
                vision_score REAL DEFAULT 0,
                vision_rationale TEXT,
                composite_score REAL DEFAULT 0,
                phash TEXT,
                query TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                chosen_id TEXT NOT NULL,
                rejected_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chosen_id) REFERENCES candidates(id)
            );

            CREATE TABLE IF NOT EXISTS download_archive (
                url TEXT PRIMARY KEY,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_candidates_query ON candidates(query);
            CREATE INDEX IF NOT EXISTS idx_candidates_phash ON candidates(phash);
        """)
        self.conn.commit()

    def save_candidates(self, candidates: list[Candidate], query: str) -> None:
        for c in candidates:
            self.conn.execute(
                """INSERT OR REPLACE INTO candidates
                   (id, url, source, source_page, title, width, height, format,
                    license, attribution, metadata, relevance_score, aesthetic_score,
                    technical_score, vision_score, vision_rationale, composite_score,
                    phash, query)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (c.id, c.url, c.source, c.source_page, c.title, c.width, c.height,
                 c.format, c.license.value, c.attribution, json.dumps(c.metadata),
                 c.relevance_score, c.aesthetic_score, c.technical_score,
                 c.vision_score, c.vision_rationale, c.composite_score, c.phash, query),
            )
        self.conn.commit()

    def get_candidate(self, candidate_id: str) -> Candidate | None:
        row = self.conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if not row and len(candidate_id) >= 4:
            row = self.conn.execute(
                "SELECT * FROM candidates WHERE id LIKE ? LIMIT 1",
                (candidate_id + "%",),
            ).fetchone()
        if not row:
            return None
        return self._row_to_candidate(row)

    def get_candidates_for_query(self, query: str) -> list[Candidate]:
        rows = self.conn.execute(
            "SELECT * FROM candidates WHERE query = ? ORDER BY composite_score DESC",
            (query,),
        ).fetchall()
        return [self._row_to_candidate(r) for r in rows]

    def record_preference(self, query: str, chosen_id: str, rejected_ids: list[str]) -> None:
        self.conn.execute(
            "INSERT INTO preferences (query, chosen_id, rejected_ids) VALUES (?, ?, ?)",
            (query, chosen_id, json.dumps(rejected_ids)),
        )
        self.conn.commit()

    def get_preferences(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM preferences ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def is_downloaded(self, url: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM download_archive WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def mark_downloaded(self, url: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO download_archive (url) VALUES (?)", (url,)
        )
        self.conn.commit()

    def _row_to_candidate(self, row: sqlite3.Row) -> Candidate:
        c = Candidate(
            url=row["url"],
            source=row["source"] or "",
            source_page=row["source_page"] or "",
            title=row["title"] or "",
            width=row["width"] or 0,
            height=row["height"] or 0,
            format=row["format"] or "",
            license=LicenseType(row["license"]) if row["license"] else LicenseType.UNKNOWN,
            attribution=row["attribution"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
        c.id = row["id"]
        c.relevance_score = row["relevance_score"] or 0.0
        c.aesthetic_score = row["aesthetic_score"] or 0.0
        c.technical_score = row["technical_score"] or 0.0
        c.vision_score = row["vision_score"] or 0.0
        c.vision_rationale = row["vision_rationale"] or ""
        c.composite_score = row["composite_score"] or 0.0
        c.phash = row["phash"] or ""
        return c

    def close(self) -> None:
        self.conn.close()
