"""Progressive, deterministic traversal of Markdown resources."""

import json
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse

from tts_ci_cd.ctx.analysis import ANALYSIS_RESULT_VERSION
from tts_ci_cd.ctx.resources import MarkdownResource, MarkdownResourceCatalog


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")


class MarkdownHeading:
    """A Markdown heading with its source location and stable anchor."""

    def __init__(self, level: int, title: str, line: int, anchor: str) -> None:
        """Create a heading descriptor.

        Args:
            level: Markdown heading level from 1 through 6.
            title: Heading text without Markdown markers.
            line: One-based source line number.
            anchor: Stable fragment identifier for the heading.
        """
        self.level = level
        self.title = title
        self.line = line
        self.anchor = anchor

    def to_dict(self) -> dict:
        """Return a JSON-compatible heading representation."""
        return {
            "anchor": self.anchor,
            "level": self.level,
            "line": self.line,
            "title": self.title,
        }


class MarkdownDocument:
    """A document-tree entry preserving its path and outline."""

    def __init__(self, path: str, headings: Tuple[MarkdownHeading, ...], revision: str) -> None:
        """Create a document-tree entry.

        Args:
            path: Resource-relative Markdown path.
            headings: Headings discovered in the document.
            revision: Standards revision associated with the resource.
        """
        self.path = path
        self.headings = headings
        self.revision = revision

    def to_dict(self) -> dict:
        """Return a JSON-compatible document representation."""
        return {
            "headings": [heading.to_dict() for heading in self.headings],
            "path": self.path,
            "revision": self.revision,
        }


class MarkdownSection:
    """A selected heading and the content belonging to it."""

    def __init__(
        self,
        path: str,
        heading: MarkdownHeading,
        text: str,
        line_start: int,
        line_end: int,
        revision: str,
    ) -> None:
        """Create a selected section.

        Args:
            path: Resource-relative Markdown path.
            heading: Heading that starts the section.
            text: Section content excluding the heading line.
            line_start: One-based first content line.
            line_end: One-based last content line.
            revision: Standards revision associated with the resource.
        """
        self.path = path
        self.heading = heading
        self.text = text
        self.line_start = line_start
        self.line_end = line_end
        self.revision = revision

    def to_dict(self) -> dict:
        """Return a JSON-compatible section representation."""
        return {
            "heading": self.heading.to_dict(),
            "line_end": self.line_end,
            "line_start": self.line_start,
            "path": self.path,
            "revision": self.revision,
            "text": self.text,
        }


class MarkdownLink:
    """A resolved local or reported external Markdown link."""

    def __init__(
        self,
        source_path: str,
        target: str,
        external: bool,
        document: Optional[MarkdownResource],
        anchor: Optional[str],
        revision: str,
    ) -> None:
        """Create a link result.

        Args:
            source_path: Resource-relative path containing the link.
            target: Link target exactly as declared in Markdown.
            external: Whether the target is external and was not fetched.
            document: Resolved local document, or `None` for external links.
            anchor: Optional fragment from the target.
            revision: Standards revision associated with the source resource.
        """
        self.source_path = source_path
        self.target = target
        self.external = external
        self.document = document
        self.anchor = anchor
        self.revision = revision

    def to_dict(self) -> dict:
        """Return a JSON-compatible link representation."""
        return {
            "anchor": self.anchor,
            "document": self.document.path if self.document else None,
            "external": self.external,
            "revision": self.revision,
            "source_path": self.source_path,
            "target": self.target,
        }


class MarkdownMatch:
    """A source-located search match in a Markdown document."""

    def __init__(self, path: str, line: int, kind: str, text: str) -> None:
        """Create a search match.

        Args:
            path: Resource-relative Markdown path.
            line: One-based source line number.
            kind: Matched surface: `text`, `heading`, `metadata`, or `link`.
            text: Complete source line containing the match.
        """
        self.path = path
        self.line = line
        self.kind = kind
        self.text = text

    def to_dict(self) -> dict:
        """Return a JSON-compatible match representation."""
        return {
            "kind": self.kind,
            "line": self.line,
            "path": self.path,
            "text": self.text,
        }


class TraversalResult:
    """Versioned envelope shared by every traversal operation's JSON output."""

    def __init__(self, operation: str, scope: str, standards_revision: str, result: Any) -> None:
        """Create a versioned traversal result.

        Args:
            operation: Traversal operation that produced the result.
            scope: Resolved documentation root the operation ran against.
            standards_revision: Standards revision associated with the resources.
            result: JSON-compatible operation payload.
        """
        self.version = ANALYSIS_RESULT_VERSION
        self.operation = operation
        self.scope = scope
        self.standards_revision = standards_revision
        self.result = result

    def to_json(self) -> str:
        """Serialize the envelope deterministically."""
        return json.dumps(
            {
                "operation": self.operation,
                "result": self.result,
                "scope": self.scope,
                "standards_revision": self.standards_revision,
                "version": self.version,
            },
            indent=2,
            sort_keys=True,
        )


class MarkdownTraversal:
    """Provide a small interface for progressive Markdown navigation."""

    def __init__(self, catalog: MarkdownResourceCatalog) -> None:
        """Create a traversal over a resource catalog.

        Args:
            catalog: Resource catalog supplying deterministic Markdown reads.
        """
        self.catalog = catalog

    def read(self, path: str) -> MarkdownResource:
        """Read one complete Markdown document."""
        return self.catalog.read_document(path)

    def tree(self) -> Tuple[MarkdownDocument, ...]:
        """Return every document and its full heading outline in path order."""
        documents = []
        for path in self.catalog.list_documents():
            resource = self.catalog.read_document(path)
            documents.append(
                MarkdownDocument(path, tuple(self._headings(resource.text)), resource.revision)
            )
        return tuple(documents)

    def outline(self, path: str, depth: int = 1) -> Tuple[MarkdownHeading, ...]:
        """Return headings through the requested Markdown heading depth.

        Args:
            path: Resource-relative Markdown path.
            depth: Maximum heading level to include, from 1 through 6.
        """
        if depth < 1 or depth > 6:
            raise ValueError("depth must be between 1 and 6")
        resource = self.catalog.read_document(path)
        return tuple(heading for heading in self._headings(resource.text) if heading.level <= depth)

    def section(self, path: str, selector: str) -> MarkdownSection:
        """Read the content under one heading, excluding the next peer section.

        Args:
            path: Resource-relative Markdown path.
            selector: Heading title or anchor to select.
        """
        resource = self.catalog.read_document(path)
        headings = self._headings(resource.text)
        selected = self._select_heading(headings, selector)
        selected_index = headings.index(selected)
        lines = resource.text.splitlines()
        end = len(lines)
        for heading in headings[selected_index + 1 :]:
            if heading.level <= selected.level:
                end = heading.line - 1
                break
        text = "\n".join(lines[selected.line : end]).strip()
        return MarkdownSection(path, selected, text, selected.line + 1, end, resource.revision)

    def follow(self, source_path: str, target: str) -> MarkdownLink:
        """Resolve a local link or report an external link without fetching it.

        Args:
            source_path: Resource-relative path containing the link.
            target: Relative Markdown target, fragment, or external URL.
        """
        parsed = urlparse(target)
        revision = self.catalog.standards_revision
        anchor = parsed.fragment or None
        if parsed.scheme or parsed.netloc:
            return MarkdownLink(source_path, target, True, None, anchor, revision)
        resolved_path = (Path(source_path).parent / parsed.path).as_posix() if parsed.path else source_path
        document = self.catalog.read_document(resolved_path)
        return MarkdownLink(source_path, target, False, document, anchor, revision)

    def search(self, query: str) -> Tuple[MarkdownMatch, ...]:
        """Search text, headings, metadata, and links without network access.

        Args:
            query: Case-insensitive text to locate in Markdown resources.
        """
        query_lower = query.lower()
        matches: List[MarkdownMatch] = []
        for path in self.catalog.list_documents():
            resource = self.catalog.read_document(path)
            in_metadata = False
            for line_number, line in enumerate(resource.text.splitlines(), 1):
                heading = _HEADING_RE.match(line)
                if heading:
                    in_metadata = heading.group(2).strip().lower() == "tts metadata"
                if query_lower not in line.lower():
                    continue
                prose = _LINK_RE.sub("", line)
                if heading:
                    kind = "heading"
                elif in_metadata:
                    kind = "metadata"
                elif query_lower not in prose.lower():
                    kind = "link"
                else:
                    kind = "text"
                matches.append(MarkdownMatch(path, line_number, kind, line))
        return tuple(sorted(matches, key=lambda match: (match.path, match.line, match.kind, match.text)))

    @staticmethod
    def _headings(text: str) -> List[MarkdownHeading]:
        headings = []
        used_anchors = {}
        for line_number, line in enumerate(text.splitlines(), 1):
            match = _HEADING_RE.match(line)
            if not match:
                continue
            title = match.group(2).strip()
            base_anchor = _slugify(title)
            occurrence = used_anchors.get(base_anchor, 0)
            used_anchors[base_anchor] = occurrence + 1
            anchor = base_anchor if occurrence == 0 else "{}-{}".format(base_anchor, occurrence)
            headings.append(MarkdownHeading(len(match.group(1)), title, line_number, anchor))
        return headings

    @staticmethod
    def _select_heading(headings: List[MarkdownHeading], selector: str) -> MarkdownHeading:
        normalized = selector.lstrip("#").lower()
        for heading in headings:
            if heading.anchor == normalized or heading.title.lower() == normalized:
                return heading
        raise ValueError("heading not found: {}".format(selector))


def _slugify(title: str) -> str:
    """Create a deterministic GitHub-style anchor from heading text."""
    slug = re.sub(r"[^a-z0-9 -]", "", title.lower())
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", slug)).strip("-")
