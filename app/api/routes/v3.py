import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_services
from app.schemas.chat import ChatRequest
from app.schemas.common import PhaseStatusResponse
from app.services.agent import AgentConfigurationError
from app.services.runtime import ApplicationServices
from app.utils.sse import encode_sse
from app.utils.text import collapse_whitespace

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=PhaseStatusResponse, summary="Phase 3 placeholder")
async def phase_three_root() -> PhaseStatusResponse:
    return PhaseStatusResponse(
        phase="v3",
        message="Phase 3 agent chat is available at POST /v3/chat.",
    )


@router.post("/chat", summary="Stream On-Call assistant responses")
async def chat(
    payload: ChatRequest,
    services: ApplicationServices = Depends(get_services),
) -> StreamingResponse:
    message = collapse_whitespace(payload.message)

    async def event_stream():
        if not message:
            yield encode_sse("error", {"message": "Message cannot be empty."})
            yield encode_sse("done", {"final_text": ""})
            return

        yield encode_sse(
            "status",
            {"message": "Assistant started. Waiting for model and tool events."},
        )

        try:
            async for event in services.agent.stream_chat(
                message=message,
                history=payload.history,
            ):
                if "stage" in event:
                    yield encode_sse("trace", event)
                    continue

                if "delta" in event:
                    yield encode_sse("token", event)
                    continue

                if "content" in event:
                    yield encode_sse("message", event)

        except AgentConfigurationError as exc:
            yield encode_sse("error", {"message": str(exc)})
            yield encode_sse("done", {"final_text": ""})
            return
        except Exception as exc:
            logger.exception("Agent streaming failed")
            yield encode_sse("error", {"message": str(exc)})
            yield encode_sse("done", {"final_text": ""})
            return

        yield encode_sse("done", {"final_text": ""})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
