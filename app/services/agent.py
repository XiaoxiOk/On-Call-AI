from __future__ import annotations

import json
from typing import Any, AsyncIterator
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.core.config import Settings
from app.schemas.chat import ChatHistoryMessage
from app.services.documents import SopRepository
from app.utils.text import collapse_whitespace, truncate_text


class AgentConfigurationError(RuntimeError):
    """Raised when the agent cannot be constructed from current settings."""


class OnCallAgentService:
    def __init__(self, repository: SopRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self._agent = None
        self._tools = self._build_tools()

    def _build_tools(self) -> list[Any]:
        repository = self.repository

        @tool
        def read_file(fname: str) -> str:
            """Read a file from the data directory by exact filename and return plain text."""

            return repository.read_file_text(fname)

        return [read_file]

    def _build_prompt(self) -> str:
        catalog = self.repository.build_catalog()
        return (
            "你是 On-Call 助手，任务是解答故障处理问题。"
            "如果不知道具体流程，或者需要确认 SOP 细节，请调用 read_file 工具读取对应 SOP 文件。\n\n"
            "约束：\n"
            "1. 不能编造 SOP 中不存在的具体步骤。\n"
            "2. 不能列目录，不能使用通配符，只能按精确文件名调用 read_file。\n"
            "3. 如果问题跨多个领域，可以读取多个 SOP 后综合回答。\n"
            "4. 回答时尽量给出排查步骤、临时缓解方案、升级条件和注意事项。\n\n"
            "已知 SOP 文件清单：\n"
            f"{catalog}"
        )

    def get_agent(self):
        if self._agent is not None:
            return self._agent

        if not self.settings.openai_api_key:
            raise AgentConfigurationError(
                "No API key is configured. Set AGENT_API_KEY in the system environment, or provide OPENAI_API_KEY."
            )

        model = ChatOpenAI(
            model=self.settings.openai_model,
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url or None,
            temperature=self.settings.openai_temperature,
            streaming=True,
        )
        self._agent = create_react_agent(
            model,
            self._tools,
            prompt=self._build_prompt(),
        )
        return self._agent

    async def stream_chat(
        self,
        *,
        message: str,
        history: list[ChatHistoryMessage],
    ) -> AsyncIterator[dict[str, Any]]:
        agent = self.get_agent()
        messages = self._build_messages(message, history)
        streamed_parts: list[str] = []
        fallback_final_text = ""

        async for event in agent.astream_events({"messages": messages}, version="v2"):
            event_name = event.get("event", "")
            data = event.get("data", {})
            name = event.get("name", "")

            if event_name == "on_tool_start":
                filename = _extract_filename(data.get("input"))
                yield {
                    "id": uuid4().hex,
                    "stage": "thought",
                    "title": "Need SOP details",
                    "content": (
                        f"准备读取 {filename} 以确认具体处理流程。"
                        if filename
                        else "准备调用 read_file 读取 SOP 细节。"
                    ),
                }
                yield {
                    "id": uuid4().hex,
                    "stage": "action",
                    "title": f"Call {name or 'read_file'}",
                    "content": _format_tool_input(data.get("input")),
                }
                continue

            if event_name == "on_tool_end":
                observation = _coerce_text(data.get("output"))
                yield {
                    "id": uuid4().hex,
                    "stage": "observation",
                    "title": f"Observation from {name or 'read_file'}",
                    "content": truncate_text(observation, limit=320),
                }
                continue

            if event_name == "on_chat_model_stream":
                delta = _extract_delta_text(data.get("chunk"))
                if delta:
                    streamed_parts.append(delta)
                    yield {"delta": delta}
                continue

            if event_name == "on_chain_end":
                maybe_text = _extract_final_text(data.get("output"))
                if maybe_text:
                    fallback_final_text = maybe_text

        final_text = "".join(streamed_parts).strip() or fallback_final_text.strip()
        yield {"content": final_text}

    def _build_messages(
        self,
        message: str,
        history: list[ChatHistoryMessage],
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = []

        for item in history:
            content = collapse_whitespace(item.content)
            if not content:
                continue

            if item.role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))

        messages.append(HumanMessage(content=collapse_whitespace(message)))
        return messages


def _extract_delta_text(chunk: Any) -> str:
    if chunk is None:
        return ""

    if hasattr(chunk, "message"):
        return _coerce_text(chunk.message)

    return _coerce_text(chunk)


def _extract_final_text(output: Any) -> str:
    if isinstance(output, dict):
        messages = output.get("messages")
        if isinstance(messages, list) and messages:
            return _coerce_text(messages[-1])
    return _coerce_text(output)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if hasattr(value, "content"):
        return _coerce_text(getattr(value, "content"))

    if isinstance(value, list):
        fragments = [_coerce_text(item) for item in value]
        return "".join(fragment for fragment in fragments if fragment)

    if isinstance(value, dict):
        if "text" in value and isinstance(value["text"], str):
            return value["text"]
        if "content" in value:
            return _coerce_text(value["content"])
        if "output_text" in value:
            return _coerce_text(value["output_text"])
        if "messages" in value:
            return _coerce_text(value["messages"])
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def _extract_filename(value: Any) -> str:
    if isinstance(value, dict):
        filename = value.get("fname")
        if isinstance(filename, str):
            return filename
    if isinstance(value, str):
        return value
    return ""


def _format_tool_input(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
