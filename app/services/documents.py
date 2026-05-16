from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from app.utils.text import collapse_whitespace


EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
SECTION_HEADING_RE = re.compile(r"^[一二三四五六七八九十0-9]+[、.．]\s*\S+")
SCENE_HEADING_RE = re.compile(r"^场景[一二三四五六七八九十0-9]+[：:]\s*\S+")
METADATA_MARKERS = (
    "文档编号",
    "版本",
    "最后更新",
    "适用范围",
    "如有疑问请联系",
    "联系方式",
    "联系：",
    "联系:",
    "本文档由",
)


@dataclass(slots=True)
class DocumentChunk:
    heading: str
    text: str

    @property
    def search_text(self) -> str:
        if self.heading:
            return f"{self.heading}\n{self.text}"
        return self.text


@dataclass(slots=True)
class DocumentRecord:
    id: str
    filename: str
    title: str
    text: str
    chunks: list[DocumentChunk]

    @property
    def search_text(self) -> str:
        return f"{self.title}\n{self.text}"


class SopRepository:
    def __init__(self, data_dir: Path, documents: list[DocumentRecord]) -> None:
        self.data_dir = data_dir.resolve()
        self.documents = documents
        self._documents_by_id = {document.id: document for document in documents}
        self._documents_by_filename = {
            document.filename: document for document in documents
        }

    @classmethod
    def load(cls, data_dir: Path) -> "SopRepository":
        resolved_dir = data_dir.resolve()
        if not resolved_dir.exists() or not resolved_dir.is_dir():
            raise FileNotFoundError(f"Data directory does not exist: {resolved_dir}")

        documents: list[DocumentRecord] = []
        for path in sorted(resolved_dir.glob("*.html")):
            html = path.read_text(encoding="utf-8")
            title, text, chunks = extract_document_from_html(html)
            documents.append(
                DocumentRecord(
                    id=path.stem.lower(),
                    filename=path.name,
                    title=title or path.stem,
                    text=text,
                    chunks=chunks,
                )
            )

        if not documents:
            raise RuntimeError(f"No HTML documents found in {resolved_dir}")

        return cls(resolved_dir, documents)

    def get_by_id(self, document_id: str) -> DocumentRecord | None:
        return self._documents_by_id.get(document_id.lower())

    def read_file_text(self, filename: str) -> str:
        candidate = self._resolve_exact_file(filename)
        if candidate.suffix.lower() == ".html":
            html = candidate.read_text(encoding="utf-8")
            _, text, _ = extract_document_from_html(html)
            return text

        return collapse_whitespace(candidate.read_text(encoding="utf-8"))

    def build_catalog(self) -> str:
        return "\n".join(
            f"- {document.filename}: {document.title}"
            for document in self.documents
        )

    def _resolve_exact_file(self, filename: str) -> Path:
        sanitized = filename.strip()
        if not sanitized:
            raise ValueError("Filename cannot be empty.")

        if Path(sanitized).name != sanitized:
            raise ValueError("Only exact filenames are allowed.")

        if any(token in sanitized for token in ("*", "?", "[", "]")):
            raise ValueError("Wildcards are not allowed.")

        candidate = (self.data_dir / sanitized).resolve()
        if candidate.parent != self.data_dir:
            raise ValueError("The requested file is outside the data directory.")

        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"File not found: {sanitized}")

        return candidate


def extract_document_from_html(html: str) -> tuple[str, str, list[DocumentChunk]]:
    soup = BeautifulSoup(html, "html.parser")

    for unwanted in soup(["script", "style"]):
        unwanted.decompose()

    title = _extract_title(soup)
    chunks = _extract_chunks(soup)
    if chunks:
        text = collapse_whitespace(
            "\n\n".join(chunk.search_text for chunk in chunks if chunk.search_text)
        )
    else:
        content_root = _select_content_root(soup)
        text = collapse_whitespace(content_root.get_text(separator=" ", strip=True))
        chunks = [DocumentChunk(heading=title, text=text)] if text else []
    return title, text, chunks


def _extract_title(soup: BeautifulSoup) -> str:
    title_candidates = [
        soup.title.get_text(" ", strip=True) if soup.title else "",
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "",
    ]

    for candidate in title_candidates:
        normalized = collapse_whitespace(candidate)
        if normalized:
            return normalized

    return "Untitled SOP"


def _extract_chunks(soup: BeautifulSoup) -> list[DocumentChunk]:
    content_root = _select_content_root(soup)
    chunks: list[DocumentChunk] = []
    current_section = ""
    current_heading = ""
    current_parts: list[str] = []

    def flush_chunk() -> None:
        nonlocal current_parts
        text = collapse_whitespace(" ".join(current_parts))
        current_parts = []
        if not text:
            return
        chunks.append(DocumentChunk(heading=current_heading, text=text))

    for line in _extract_content_lines(content_root):
        if SCENE_HEADING_RE.match(line):
            flush_chunk()
            current_heading = (
                f"{current_section} / {line}" if current_section else line
            )
            continue

        if SECTION_HEADING_RE.match(line):
            flush_chunk()
            current_section = line
            current_heading = line
            continue

        if not current_heading or _should_skip_metadata(line):
            continue
        current_parts.append(line)

    flush_chunk()

    filtered = [
        chunk
        for chunk in chunks
        if chunk.text and not _should_skip_metadata(chunk.search_text)
    ]
    if filtered:
        return filtered

    fallback_text = collapse_whitespace(content_root.get_text(separator=" ", strip=True))
    return [DocumentChunk(heading="", text=fallback_text)] if fallback_text else []


def _select_content_root(soup: BeautifulSoup) -> Tag:
    if main := soup.find("main"):
        return main

    if body := soup.body:
        for wrapper in body.find_all(["header", "footer"]):
            wrapper.decompose()
        return body

    return soup


def _extract_content_lines(content_root: Tag) -> list[str]:
    lines: list[str] = []
    for raw_line in content_root.get_text("\n", strip=True).splitlines():
        normalized = collapse_whitespace(raw_line)
        if normalized:
            lines.append(normalized)
    return lines


def _should_skip_metadata(text: str) -> bool:
    if not text:
        return True

    lowered = text.casefold()
    if EMAIL_RE.search(text):
        return True

    for marker in METADATA_MARKERS:
        if marker.casefold() in lowered:
            return True

    return False
