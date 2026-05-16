from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from app.utils.text import collapse_whitespace


@dataclass(slots=True)
class DocumentRecord:
    id: str
    filename: str
    title: str
    text: str

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
            title, text = extract_document_from_html(html)
            documents.append(
                DocumentRecord(
                    id=path.stem.lower(),
                    filename=path.name,
                    title=title or path.stem,
                    text=text,
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
            _, text = extract_document_from_html(html)
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


def extract_document_from_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for unwanted in soup(["script", "style"]):
        unwanted.decompose()

    title = _extract_title(soup)
    text = collapse_whitespace(soup.get_text(separator=" ", strip=True))
    return title, text


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
