from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.agent import OnCallAgentService
from app.services.documents import SopRepository
from app.services.search import KeywordSearchService, SemanticSearchService


@dataclass(slots=True)
class ApplicationServices:
    repository: SopRepository
    keyword_search: KeywordSearchService
    semantic_search: SemanticSearchService
    agent: OnCallAgentService


def build_application_services(settings: Settings) -> ApplicationServices:
    repository = SopRepository.load(settings.data_dir)
    keyword_search = KeywordSearchService(
        repository,
        default_limit=settings.search_top_k,
    )
    semantic_search = SemanticSearchService(
        repository,
        default_limit=settings.semantic_top_k,
        model_name=settings.embedding_model_name,
        query_instruction=settings.embedding_query_instruction,
    )
    semantic_search.initialize()
    agent = OnCallAgentService(repository, settings)
    return ApplicationServices(
        repository=repository,
        keyword_search=keyword_search,
        semantic_search=semantic_search,
        agent=agent,
    )
