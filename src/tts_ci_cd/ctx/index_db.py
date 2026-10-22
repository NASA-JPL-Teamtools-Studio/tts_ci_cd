"""SQLite index database for tts-ctx.

Stores modules, classes, symbols (methods/functions), inheritance links,
and imports across the entire TTS workspace.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tts_ci_cd.ctx.config import get_csv_dump_dir, get_db_path


class IndexDB:
    """SQLite-backed store for the TTS symbol index."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            # --- Repos ---
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS repos (
                    name TEXT PRIMARY KEY,
                    path TEXT,
                    group_dir TEXT,
                    git_remote TEXT,
                    ownership TEXT,
                    adapts TEXT,
                    type TEXT,
                    mission TEXT,
                    summary TEXT
                )
            """)
            # Retrofit older DBs created before the summary column existed.
            try:
                self.conn.execute("ALTER TABLE repos ADD COLUMN summary TEXT")
            except sqlite3.OperationalError:
                pass
            # --- Modules (Python files as dotted paths) ---
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS modules (
                    id INTEGER PRIMARY KEY,
                    repo_name TEXT,
                    dotted_path TEXT,
                    file_path TEXT,
                    package_root TEXT,
                    UNIQUE(dotted_path)
                )
            """)
            # --- Imports within a module ---
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS imports (
                    module_id INTEGER,
                    alias TEXT,
                    resolved_module TEXT,
                    resolved_name TEXT,
                    FOREIGN KEY(module_id) REFERENCES modules(id)
                )
            """)
            # --- Classes ---
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY,
                    module_id INTEGER,
                    name TEXT,
                    full_path TEXT UNIQUE,
                    doc_summary TEXT,
                    is_public BOOLEAN,
                    line_start INTEGER,
                    line_end INTEGER,
                    FOREIGN KEY(module_id) REFERENCES modules(id)
                )
            """)
            # --- Symbols (methods and functions) ---
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY,
                    class_id INTEGER,
                    module_id INTEGER,
                    name TEXT,
                    full_path TEXT UNIQUE,
                    signature TEXT,
                    doc_summary TEXT,
                    is_public BOOLEAN,
                    line_start INTEGER,
                    line_end INTEGER,
                    kind TEXT,
                    FOREIGN KEY(class_id) REFERENCES classes(id),
                    FOREIGN KEY(module_id) REFERENCES modules(id)
                )
            """)
            # --- Inheritance ---
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS inheritance (
                    child_class_id INTEGER,
                    parent_class_id INTEGER,
                    parent_external TEXT,
                    PRIMARY KEY(child_class_id, parent_class_id, parent_external)
                )
            """)
            # --- Raw base class expressions (for Pass 2 resolution) ---
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS class_bases (
                    class_id INTEGER,
                    base_repr TEXT,
                    FOREIGN KEY(class_id) REFERENCES classes(id)
                )
            """)

    def close(self):
        if self.conn:
            self.conn.close()

    # === Insert helpers ===

    def add_repo(self, name: str, path: str, group_dir: str, git_remote: Optional[str],
                  ownership: str, adapts: Optional[str], repo_type: str = "incidental", mission: Optional[str] = None,
                  summary: Optional[str] = None):
        with self.conn:
            self.conn.execute(
                """INSERT OR REPLACE INTO repos (name, path, group_dir, git_remote, ownership, adapts, type, mission, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, path, group_dir, git_remote, ownership, adapts, repo_type, mission, summary),
            )

    def add_module(self, repo_name: str, dotted_path: str, file_path: str, package_root: str) -> int:
        with self.conn:
            cursor = self.conn.execute(
                """INSERT OR REPLACE INTO modules (repo_name, dotted_path, file_path, package_root)
                   VALUES (?, ?, ?, ?)""",
                (repo_name, dotted_path, file_path, package_root),
            )
            return cursor.lastrowid

    def add_import(self, module_id: int, alias: str, resolved_module: Optional[str],
                    resolved_name: Optional[str]):
        with self.conn:
            self.conn.execute(
                "INSERT INTO imports (module_id, alias, resolved_module, resolved_name) VALUES (?, ?, ?, ?)",
                (module_id, alias, resolved_module, resolved_name),
            )

    def add_class(self, module_id: int, name: str, full_path: str, doc_summary: str,
                  is_public: bool, line_start: int, line_end: int) -> int:
        with self.conn:
            cursor = self.conn.execute(
                """INSERT OR REPLACE INTO classes (module_id, name, full_path, doc_summary, is_public, line_start, line_end)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (module_id, name, full_path, doc_summary, is_public, line_start, line_end),
            )
            return cursor.lastrowid

    def add_symbol(self, class_id: Optional[int], module_id: int, name: str,
                    full_path: str, signature: str, doc_summary: str, is_public: bool,
                    line_start: int, line_end: int, kind: str):
        with self.conn:
            self.conn.execute(
                """INSERT OR REPLACE INTO symbols
                   (class_id, module_id, name, full_path, signature, doc_summary, is_public, line_start, line_end, kind)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (class_id, module_id, name, full_path, signature, doc_summary, is_public,
                 line_start, line_end, kind),
            )

    def add_inheritance_internal(self, child_id: int, parent_id: int):
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO inheritance (child_class_id, parent_class_id, parent_external) VALUES (?, ?, NULL)",
                (child_id, parent_id),
            )

    def add_inheritance_external(self, child_id: int, external_name: str):
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO inheritance (child_class_id, parent_class_id, parent_external) VALUES (?, NULL, ?)",
                (child_id, external_name),
            )

    # === Query helpers ===

    def get_class_by_path(self, full_path: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM classes WHERE full_path = ?", (full_path,)
        ).fetchone()

    def get_class_mro(self, class_id: int) -> List[Tuple[Optional[int], str, Optional[str]]]:
        """Return [(class_id, class_name, external_name_or_None), ...] in MRO order.

        Walks the inheritance chain depth-first.
        """
        mro = []
        seen = set()

        def visit(cid: int):
            if cid in seen:
                return
            seen.add(cid)
            row = self.conn.execute(
                "SELECT id, full_path FROM classes WHERE id = ?", (cid,)
            ).fetchone()
            if row:
                mro.append((cid, row["full_path"], None))
            parents = self.conn.execute(
                """SELECT parent_class_id, parent_external FROM inheritance WHERE child_class_id = ?""",
                (cid,)
            ).fetchall()
            for parent in parents:
                if parent["parent_class_id"] is not None:
                    visit(parent["parent_class_id"])
                elif parent["parent_external"]:
                    mro.append((None, None, parent["parent_external"]))

        visit(class_id)
        return mro

    def get_class_methods(self, class_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            """SELECT name, full_path, signature, doc_summary, is_public, line_start, line_end
               FROM symbols WHERE class_id = ? AND kind = 'method' ORDER by is_public DESC, name""",
            (class_id,)
        ).fetchall()

    def get_class_by_id(self, class_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()

    def get_module_by_id(self, module_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM modules WHERE id = ?", (module_id,)).fetchone()

    def search_symbols(self, query: str, repo_filter: Optional[str] = None) -> List[Dict]:
        """Search across class/symbol names, doc summaries, and module paths.

        Results are ranked: exact name match > name startswith query >
        name contains query > doc_summary/module path contains query.
        Each result carries a `matched_on` field explaining the hit.
        """
        like = f"%{query}%"
        if repo_filter:
            rows = self.conn.execute(
                """SELECT c.name, c.full_path, 'class' AS kind, c.doc_summary, m.repo_name
                   FROM classes c
                   JOIN modules m ON c.module_id = m.id
                   WHERE (c.name LIKE ? OR c.doc_summary LIKE ? OR m.dotted_path LIKE ?)
                     AND m.repo_name LIKE ?
                   UNION
                   SELECT s.name, s.full_path, s.kind, s.doc_summary, m.repo_name
                   FROM symbols s
                   JOIN modules m ON s.module_id = m.id
                   WHERE (s.name LIKE ? OR s.doc_summary LIKE ? OR m.dotted_path LIKE ?)
                     AND m.repo_name LIKE ?""",
                (like, like, like, f"%{repo_filter}%", like, like, like, f"%{repo_filter}%")
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT c.name, c.full_path, 'class' AS kind, c.doc_summary, m.repo_name
                   FROM classes c
                   JOIN modules m ON c.module_id = m.id
                   WHERE c.name LIKE ? OR c.doc_summary LIKE ? OR m.dotted_path LIKE ?
                   UNION
                   SELECT s.name, s.full_path, s.kind, s.doc_summary, m.repo_name
                   FROM symbols s
                   JOIN modules m ON s.module_id = m.id
                   WHERE s.name LIKE ? OR s.doc_summary LIKE ? OR m.dotted_path LIKE ?""",
                (like, like, like, like, like, like)
            ).fetchall()

        query_lower = query.lower()
        results = []
        for r in rows:
            name_lower = (r["name"] or "").lower()
            if name_lower == query_lower:
                tier, matched_on = 0, "name (exact)"
            elif name_lower.startswith(query_lower):
                tier, matched_on = 1, "name (prefix)"
            elif query_lower in name_lower:
                tier, matched_on = 2, "name"
            elif query_lower in (r["doc_summary"] or "").lower():
                tier, matched_on = 3, "docstring"
            else:
                tier, matched_on = 4, "module path"
            d = dict(r)
            d["tier"] = tier
            d["matched_on"] = matched_on
            results.append(d)

        results.sort(key=lambda d: (d["tier"], d["kind"], d["full_path"]))

        # Cap how many low-relevance (tier 3+) hits can crowd out everything
        # else -- e.g. a module literally named after the query shouldn't
        # flood the result list with every symbol it contains.
        capped: List[Dict] = []
        tier_counts: Dict[int, int] = {}
        for d in results:
            tier_counts[d["tier"]] = tier_counts.get(d["tier"], 0) + 1
            if d["tier"] >= 3 and tier_counts[d["tier"]] > 8:
                continue
            capped.append(d)
            if len(capped) >= 40:
                break
        return capped

    def search_classes_by_name(self, name: str) -> List[sqlite3.Row]:
        """Exact-ish match for a class by bare name (used for MRO resolution)."""
        return self.conn.execute(
            "SELECT * FROM classes WHERE name = ?", (name,)
        ).fetchall()

    def get_imports_for_module(self, module_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM imports WHERE module_id = ?", (module_id,)).fetchall()

    def get_all_repos(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM repos ORDER BY group_dir, name").fetchall()

    def get_repo_by_name(self, name: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM repos WHERE name = ?", (name,)).fetchone()

    def get_repo_structure(self, repo_name: str) -> Dict[str, object]:
        """Module/package counts and top-level sub-packages for a repo."""
        modules = self.conn.execute(
            "SELECT dotted_path, package_root FROM modules WHERE repo_name = ?",
            (repo_name,)
        ).fetchall()

        packages = sorted({m["package_root"] for m in modules if m["package_root"]})
        subpackages: Set[str] = set()
        for m in modules:
            parts = (m["dotted_path"] or "").split(".")
            if len(parts) >= 2:
                subpackages.add(".".join(parts[:2]))

        return {
            "module_count": len(modules),
            "packages": packages,
            "subpackages": sorted(subpackages),
        }

    def get_key_classes_for_repo(self, repo_name: str, limit: int = 8) -> List[sqlite3.Row]:
        return self.conn.execute(
            """SELECT c.* FROM classes c
               JOIN modules m ON c.module_id = m.id
               WHERE m.repo_name = ? AND c.is_public = 1 AND c.name NOT LIKE 'Test%'
               ORDER BY c.id LIMIT ?""",
            (repo_name, limit)
        ).fetchall()

    # === CSV dumps ===

    def dump_csvs(self, dump_dir: Optional[Path] = None):
        """Dump key tables as CSV files for git-diffability."""
        dump_dir = dump_dir or get_csv_dump_dir()
        dump_dir.mkdir(parents=True, exist_ok=True)
        tables = ["repos", "classes", "symbols", "inheritance", "modules", "imports"]
        for table in tables:
            cursor = self.conn.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            csv_path = dump_dir / f"{table}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
