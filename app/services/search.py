from __future__ import annotations

import re
from dataclasses import dataclass

import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.schemas.search import SearchResult
from app.services.documents import DocumentChunk, DocumentRecord, SopRepository
from app.utils.text import build_highlighted_snippet, collapse_whitespace


ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*|&")
COLLOQUIAL_OUTAGE_MARKERS = ("挂了", "挂掉", "宕机")
COLLOQUIAL_OUTAGE_EXPANSION = (
    "服务 超时 节点 集群 Kubernetes Ingress API Server"
)
SEMANTIC_BM25_WEIGHT = 0.1
SEMANTIC_TITLE_WEIGHT = 0.05


@dataclass(slots=True)
class SearchHit:
    document: DocumentRecord
    score: float


@dataclass(slots=True)
class ChunkReference:
    document_index: int
    chunk: DocumentChunk


@dataclass(slots=True)
class HybridScore:
    document: DocumentRecord
    best_chunk: DocumentChunk
    dense_score: float
    bm25_score: float
    title_score: float
    final_score: float


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
            scores = self.get_document_scores(normalized_query)
            for index, base_score in enumerate(scores):
                score = float(base_score)
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

    def get_document_scores(self, query: str) -> np.ndarray:
        normalized_query = collapse_whitespace(query)
        query_tokens = tokenize_for_index(normalized_query)
        scores = np.zeros(len(self.repository.documents), dtype=np.float32)
        if not query_tokens:
            return scores

        base_scores = np.asarray(self._bm25.get_scores(query_tokens), dtype=float)
        for index, base_score in enumerate(base_scores):
            boosted = self._boost_keyword_score(
                document=self.repository.documents[int(index)],
                query=normalized_query,
                base_score=float(base_score),
            )
            scores[int(index)] = max(0.0, float(boosted))

        return scores

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
        keyword_search: KeywordSearchService,
        default_limit: int,
        model_name: str,
        query_instruction: str,
    ) -> None:
        self.repository = repository
        self.keyword_search = keyword_search
        self.default_limit = default_limit
        self.model_name = model_name
        self.query_instruction = query_instruction
        self._model: SentenceTransformer | None = None
        self._chunk_embeddings: np.ndarray | None = None
        self._title_embeddings: np.ndarray | None = None
        self._chunk_references: list[ChunkReference] = []
        self._startup_error: str | None = None

    def initialize(self) -> None:
        if (
            self._model is not None
            and self._chunk_embeddings is not None
            and self._title_embeddings is not None
        ):
            return

        try:
            model = _load_sentence_transformer(self.model_name)
            chunk_references = _build_chunk_references(self.repository.documents)
            chunk_embeddings = model.encode(
                [
                    _build_chunk_embedding_text(
                        document=self.repository.documents[reference.document_index],
                        chunk=reference.chunk,
                    )
                    for reference in chunk_references
                ],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            title_embeddings = model.encode(
                [document.title for document in self.repository.documents],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self._model = model
            self._chunk_references = chunk_references
            self._chunk_embeddings = np.asarray(chunk_embeddings, dtype=np.float32)
            self._title_embeddings = np.asarray(title_embeddings, dtype=np.float32)
            self._startup_error = None
        except Exception as exc:
            self._model = None
            self._chunk_embeddings = None
            self._title_embeddings = None
            self._chunk_references = []
            self._startup_error = str(exc)

    def search(self, query: str, *, limit: int | None = None) -> list[SearchResult]:
        normalized_query = collapse_whitespace(query)
        if not normalized_query:
            return []

        self.initialize()
        if (
            self._model is None
            or self._chunk_embeddings is None
            or self._title_embeddings is None
        ):
            detail = self._startup_error or "Semantic search model is not available."
            raise SemanticSearchUnavailableError(detail)

        requested_limit = limit or self.default_limit
        ranked_scores = self._score_documents(normalized_query)
        snippet_terms = build_highlight_terms(normalized_query)

        return [
            SearchResult(
                id=hit.document.id,
                title=hit.document.title,
                snippet=build_highlighted_snippet(
                    hit.best_chunk.search_text,
                    terms=snippet_terms,
                ),
                score=round(hit.final_score, 6),
            )
            for hit in ranked_scores[:requested_limit]
        ]

    def _score_documents(self, query: str) -> list[HybridScore]:
        if (
            self._model is None
            or self._chunk_embeddings is None
            or self._title_embeddings is None
        ):
            detail = self._startup_error or "Semantic search model is not available."
            raise SemanticSearchUnavailableError(detail)

        encoded_query = self._model.encode(
            self._format_query(query),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_vector = np.asarray(encoded_query, dtype=np.float32)
        chunk_scores = np.dot(self._chunk_embeddings, query_vector)
        title_scores = np.dot(self._title_embeddings, query_vector)
        bm25_scores = self.keyword_search.get_document_scores(query)
        normalized_bm25 = _min_max_normalize(bm25_scores)

        best_chunk_scores, best_chunk_indices = _select_best_chunks(
            chunk_scores=chunk_scores,
            chunk_references=self._chunk_references,
            document_count=len(self.repository.documents),
        )

        ranked_scores: list[HybridScore] = []
        for document_index, document in enumerate(self.repository.documents):
            chunk_reference = self._chunk_references[int(best_chunk_indices[document_index])]
            dense_score = float(best_chunk_scores[document_index])
            bm25_score = float(normalized_bm25[document_index])
            title_score = max(0.0, float(title_scores[document_index]))
            # Keep chunk semantics as the primary signal and use BM25/title
            # only as lightweight boosts for exact terminology and domain hints.
            final_score = (
                dense_score
                + SEMANTIC_BM25_WEIGHT * bm25_score
                + SEMANTIC_TITLE_WEIGHT * title_score
            )
            ranked_scores.append(
                HybridScore(
                    document=document,
                    best_chunk=chunk_reference.chunk,
                    dense_score=dense_score,
                    bm25_score=bm25_score,
                    title_score=title_score,
                    final_score=float(final_score),
                )
            )

        ranked_scores.sort(key=lambda item: item.final_score, reverse=True)
        return ranked_scores

    def _format_query(self, query: str) -> str:
        normalized = _expand_semantic_query(collapse_whitespace(query))
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


def _build_chunk_references(documents: list[DocumentRecord]) -> list[ChunkReference]:
    references: list[ChunkReference] = []
    for document_index, document in enumerate(documents):
        document_chunks = document.chunks or [DocumentChunk(heading="", text=document.text)]
        for chunk in document_chunks:
            if chunk.text:
                references.append(
                    ChunkReference(
                        document_index=document_index,
                        chunk=chunk,
                    )
                )
    return references


def _build_chunk_embedding_text(
    *,
    document: DocumentRecord,
    chunk: DocumentChunk,
) -> str:
    return f"{document.title}\n{chunk.search_text}"


def _select_best_chunks(
    *,
    chunk_scores: np.ndarray,
    chunk_references: list[ChunkReference],
    document_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    best_scores = np.full(document_count, -np.inf, dtype=np.float32)
    best_indices = np.full(document_count, -1, dtype=np.int32)

    for chunk_index, score in enumerate(chunk_scores):
        document_index = chunk_references[chunk_index].document_index
        if score > best_scores[document_index]:
            best_scores[document_index] = float(score)
            best_indices[document_index] = chunk_index

    if np.any(best_indices < 0):
        raise RuntimeError("Every document must have at least one retrievable chunk.")

    return best_scores, best_indices


def _min_max_normalize(scores: np.ndarray) -> np.ndarray:
    numeric_scores = np.asarray(scores, dtype=np.float32)
    if numeric_scores.size == 0:
        return numeric_scores

    minimum = float(np.min(numeric_scores))
    maximum = float(np.max(numeric_scores))
    if np.isclose(maximum, minimum):
        return np.zeros_like(numeric_scores, dtype=np.float32)

    return (numeric_scores - minimum) / (maximum - minimum)


def _expand_semantic_query(query: str) -> str:
    if not query:
        return ""

    expansions = [query]
    has_service_target = "服务器" in query or "服务" in query
    has_colloquial_outage = any(marker in query for marker in COLLOQUIAL_OUTAGE_MARKERS)
    if has_service_target and has_colloquial_outage:
        expansions.append(COLLOQUIAL_OUTAGE_EXPANSION)

    return collapse_whitespace(" ".join(expansions))
