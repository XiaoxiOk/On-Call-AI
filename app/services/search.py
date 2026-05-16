from __future__ import annotations

import re
from dataclasses import dataclass

import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.schemas.search import SearchResult
from app.services.documents import DocumentRecord, SopRepository
from app.utils.text import build_highlighted_snippet, collapse_whitespace


ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*|&")


@dataclass(slots=True)
class SearchHit:
    document: DocumentRecord
    score: float


class KeywordSearchService:
    def __init__(self, repository: SopRepository, *, default_limit: int) -> None:
        self.repository = repository
        self.default_limit = default_limit
        self._tokenized_documents = [
            tokenize_for_index(document.search_text)
            for document in self.repository.documents
        ]
        self._bm25 = BM25Okapi(self._tokenized_documents)

    def search(self, query: str, *, limit: int | None = None) -> list[SearchResult]:
        normalized_query = collapse_whitespace(query)
        query_tokens = tokenize_for_index(normalized_query)
        requested_limit = limit or self.default_limit
        hits: list[SearchHit] = []

        if query_tokens:
            scores = np.asarray(self._bm25.get_scores(query_tokens), dtype=float)
            for index, base_score in enumerate(scores):
                score = self._boost_keyword_score(
                    document=self.repository.documents[int(index)],
                    query=normalized_query,
                    base_score=float(base_score),
                )
                if score <= 0:
                    continue
                hits.append(
                    SearchHit(
                        document=self.repository.documents[int(index)],
                        score=score,
                    )
                )
            hits.sort(key=lambda item: item.score, reverse=True)

        if not hits:
            hits = self._literal_fallback_search(normalized_query)

        snippet_terms = build_highlight_terms(normalized_query)
        return [
            SearchResult(
                id=hit.document.id,
                title=hit.document.title,
                snippet=build_highlighted_snippet(
                    hit.document.text,
                    terms=snippet_terms,
                ),
                score=round(hit.score, 6),
            )
            for hit in hits[:requested_limit]
        ]

    def _literal_fallback_search(self, query: str) -> list[SearchHit]:
        if not query:
            return []

        lowered_query = query.casefold()
        results: list[SearchHit] = []
        for document in self.repository.documents:
            haystack = document.search_text.casefold()
            count = haystack.count(lowered_query)
            if count:
                results.append(SearchHit(document=document, score=float(count)))

        return sorted(results, key=lambda item: item.score, reverse=True)

    def _boost_keyword_score(
        self,
        *,
        document: DocumentRecord,
        query: str,
        base_score: float,
    ) -> float:
        if not query:
            return base_score

        haystack = document.search_text.casefold()
        title = document.title.casefold()
        needle = query.casefold()
        literal_count = haystack.count(needle)
        title_count = title.count(needle)
        first_pos = haystack.find(needle)
        proximity_bonus = 0.0 if first_pos < 0 else max(0.0, 1.0 - first_pos / 5000)
        return base_score + literal_count * 2.0 + title_count * 3.0 + proximity_bonus


class SemanticSearchUnavailableError(RuntimeError):
    """Raised when the semantic search model is not available."""


class SemanticSearchService:
    def __init__(
        self,
        repository: SopRepository,
        *,
        default_limit: int,
        model_name: str,
        query_instruction: str,
    ) -> None:
        self.repository = repository
        self.default_limit = default_limit
        self.model_name = model_name
        self.query_instruction = query_instruction
        self._model: SentenceTransformer | None = None
        self._document_embeddings: np.ndarray | None = None
        self._startup_error: str | None = None

    def initialize(self) -> None:
        if self._model is not None and self._document_embeddings is not None:
            return

        try:
            model = _load_sentence_transformer(self.model_name)
            source_texts = [
                document.search_text for document in self.repository.documents
            ]
            embeddings = model.encode(
                source_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self._model = model
            self._document_embeddings = np.asarray(embeddings, dtype=np.float32)
            self._startup_error = None
        except Exception as exc:
            self._model = None
            self._document_embeddings = None
            self._startup_error = str(exc)

    def search(self, query: str, *, limit: int | None = None) -> list[SearchResult]:
        self.initialize()
        if self._model is None or self._document_embeddings is None:
            detail = self._startup_error or "Semantic search model is not available."
            raise SemanticSearchUnavailableError(detail)

        requested_limit = limit or self.default_limit
        encoded_query = self._model.encode(
            self._format_query(query),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_vector = np.asarray(encoded_query, dtype=np.float32)
        similarities = np.dot(self._document_embeddings, query_vector)
        snippet_terms = build_highlight_terms(query)

        results: list[SearchResult] = []
        for index in np.argsort(similarities)[::-1][:requested_limit]:
            score = float(similarities[int(index)])
            document = self.repository.documents[int(index)]
            results.append(
                SearchResult(
                    id=document.id,
                    title=document.title,
                    snippet=build_highlighted_snippet(
                        document.text,
                        terms=snippet_terms,
                    ),
                    score=round(score, 6),
                )
            )

        return results

    def _format_query(self, query: str) -> str:
        normalized = collapse_whitespace(query)
        return f"{self.query_instruction}{normalized}"


def tokenize_for_index(text: str) -> list[str]:
    normalized = collapse_whitespace(text)
    tokens: list[str] = []

    for token in jieba.lcut(normalized):
        stripped = token.strip().lower()
        if stripped:
            tokens.append(stripped)

    for token in ASCII_TOKEN_RE.findall(normalized):
        lowered = token.lower()
        if lowered not in tokens:
            tokens.append(lowered)

    return tokens


def build_highlight_terms(query: str) -> list[str]:
    normalized = collapse_whitespace(query)
    terms: list[str] = []

    if normalized:
        terms.append(normalized)

    for token in jieba.lcut(normalized):
        stripped = token.strip()
        if stripped and stripped not in terms:
            terms.append(stripped)

    for token in ASCII_TOKEN_RE.findall(normalized):
        if token and token not in terms:
            terms.append(token)

    return terms


def _load_sentence_transformer(model_name: str) -> SentenceTransformer:
    try:
        return SentenceTransformer(model_name)
    except Exception:
        return SentenceTransformer(model_name, local_files_only=True)
