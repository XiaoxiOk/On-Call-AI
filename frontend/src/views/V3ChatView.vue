<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { showFailToast } from 'vant'

import { streamSse } from '../lib/sse'
import type {
  AgentDonePayload,
  AgentErrorPayload,
  AgentMessagePayload,
  AgentTokenPayload,
  AgentTracePayload,
  ChatHistoryMessage,
  ChatRequest,
} from '../types/api'

type TranscriptEntry =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'assistant'; text: string }
  | {
      id: string
      kind: 'trace'
      stage: AgentTracePayload['stage']
      title: string
      text: string
    }
  | { id: string; kind: 'error'; text: string }

const examples = [
  '数据库主从延迟超过30秒怎么处理？',
  '服务 OOM 了怎么办？',
  'P0 故障的响应流程是什么？',
  '推荐结果质量下降了',
]

const draft = ref('服务 OOM 了怎么办？')
const sending = ref(false)
const entries = ref<TranscriptEntry[]>([])
const transcriptRef = ref<HTMLElement | null>(null)
const activeAssistantId = ref<string | null>(null)

function createId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function buildHistoryPayload(): ChatHistoryMessage[] {
  return entries.value
    .filter(
      (entry): entry is Extract<TranscriptEntry, { kind: 'user' | 'assistant' }> =>
        entry.kind === 'user' || entry.kind === 'assistant',
    )
    .map((entry) => ({
      role: entry.kind,
      content: entry.text,
    }))
}

function ensureAssistantEntry(): Extract<TranscriptEntry, { kind: 'assistant' }> {
  if (activeAssistantId.value) {
    const existing = entries.value.find(
      (entry): entry is Extract<TranscriptEntry, { kind: 'assistant' }> =>
        entry.kind === 'assistant' && entry.id === activeAssistantId.value,
    )
    if (existing) {
      return existing
    }
  }

  const entry: Extract<TranscriptEntry, { kind: 'assistant' }> = {
    id: createId('assistant'),
    kind: 'assistant',
    text: '',
  }
  activeAssistantId.value = entry.id
  entries.value.push(entry)
  return entry
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  transcriptRef.value?.scrollTo({
    top: transcriptRef.value.scrollHeight,
    behavior: 'smooth',
  })
}

function parseEventData<T>(raw: string): T {
  return JSON.parse(raw) as T
}

function handleTrace(payload: AgentTracePayload): void {
  entries.value.push({
    id: payload.id || createId('trace'),
    kind: 'trace',
    stage: payload.stage,
    title: payload.title,
    text: payload.content,
  })
  void scrollToBottom()
}

function handleToken(payload: AgentTokenPayload): void {
  const assistant = ensureAssistantEntry()
  assistant.text += payload.delta
  void scrollToBottom()
}

function handleMessage(payload: AgentMessagePayload): void {
  if (!payload.content) {
    return
  }

  const assistant = ensureAssistantEntry()
  if (!assistant.text || payload.content.length > assistant.text.length) {
    assistant.text = payload.content
  }
  void scrollToBottom()
}

function handleError(payload: AgentErrorPayload): void {
  entries.value.push({
    id: createId('error'),
    kind: 'error',
    text: payload.message,
  })
  void scrollToBottom()
}

async function sendMessage(nextDraft?: string): Promise<void> {
  if (nextDraft !== undefined) {
    draft.value = nextDraft
  }

  const message = draft.value.trim()
  if (!message || sending.value) {
    return
  }

  const history = buildHistoryPayload()
  entries.value.push({
    id: createId('user'),
    kind: 'user',
    text: message,
  })

  draft.value = ''
  sending.value = true
  activeAssistantId.value = null
  void scrollToBottom()

  const payload: ChatRequest = {
    message,
    history,
  }

  try {
    await streamSse(
      '/v3/chat',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      },
      (event) => {
        if (event.event === 'status') {
          return
        }

        if (event.event === 'trace') {
          handleTrace(parseEventData<AgentTracePayload>(event.data))
          return
        }

        if (event.event === 'token') {
          handleToken(parseEventData<AgentTokenPayload>(event.data))
          return
        }

        if (event.event === 'message') {
          handleMessage(parseEventData<AgentMessagePayload>(event.data))
          return
        }

        if (event.event === 'error') {
          handleError(parseEventData<AgentErrorPayload>(event.data))
          return
        }

        if (event.event === 'done') {
          const done = parseEventData<AgentDonePayload>(event.data)
          if (done.final_text) {
            handleMessage({ content: done.final_text })
          }
        }
      },
    )
  } catch (cause) {
    const message =
      cause instanceof Error ? cause.message : '流式对话失败，请稍后重试。'
    handleError({ message })
    showFailToast(message)
  } finally {
    sending.value = false
    activeAssistantId.value = null
  }
}
</script>

<template>
  <section class="section-stack">
    <div class="chat-lead">
      <div>
        <p class="eyebrow">Phase 3</p>
        <h2>On-Call 助手</h2>
      </div>
      <p class="chat-copy">
        对话接口使用 `POST /v3/chat`，后端通过 SSE 推送最终回答和工具调用过程。
      </p>
    </div>

    <div class="example-row">
      <van-button
        v-for="example in examples"
        :key="example"
        plain
        round
        size="small"
        @click="void sendMessage(example)"
      >
        {{ example }}
      </van-button>
    </div>

    <div ref="transcriptRef" class="transcript-panel">
      <van-empty
        v-if="!entries.length"
        description="输入问题后，助手会流式输出回答，并显示工具调用过程。"
      />

      <div v-for="entry in entries" :key="entry.id" class="entry-row">
        <div
          v-if="entry.kind === 'user'"
          class="message-bubble message-user"
        >
          <p class="bubble-label">User</p>
          <p>{{ entry.text }}</p>
        </div>

        <div
          v-else-if="entry.kind === 'assistant'"
          class="message-bubble message-assistant"
        >
          <p class="bubble-label">Assistant</p>
          <p>{{ entry.text }}</p>
        </div>

        <div
          v-else-if="entry.kind === 'trace'"
          class="trace-card"
          :class="`trace-${entry.stage}`"
        >
          <p class="trace-stage">{{ entry.stage }}</p>
          <h3>{{ entry.title }}</h3>
          <p>{{ entry.text }}</p>
        </div>

        <div v-else class="message-bubble message-error">
          <p class="bubble-label">Error</p>
          <p>{{ entry.text }}</p>
        </div>
      </div>

      <div v-if="sending" class="streaming-indicator">
        <van-loading size="18px" /> 助手正在思考并读取 SOP
      </div>
    </div>

    <div class="composer">
      <van-field
        v-model="draft"
        rows="3"
        autosize
        type="textarea"
        maxlength="1000"
        show-word-limit
        placeholder="输入你的 On-Call 问题，例如：数据库主从延迟超过30秒怎么处理？"
      />
      <van-button
        type="warning"
        block
        :loading="sending"
        @click="void sendMessage()"
      >
        发送问题
      </van-button>
    </div>
  </section>
</template>

<style scoped>
.chat-lead {
  display: grid;
  gap: 8px;
}

.chat-lead h2 {
  margin: 0;
  font-size: 28px;
}

.chat-copy {
  margin: 0;
  color: #5b6475;
}

.example-row {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(180px, max-content));
}

.transcript-panel {
  min-height: 420px;
  max-height: 68vh;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(240, 249, 255, 0.82));
}

.entry-row + .entry-row {
  margin-top: 14px;
}

.message-bubble,
.trace-card {
  max-width: 88%;
  padding: 14px 16px;
  border-radius: 22px;
  white-space: pre-wrap;
  line-height: 1.7;
}

.message-bubble p,
.trace-card p,
.trace-card h3 {
  margin: 0;
}

.bubble-label,
.trace-stage {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.message-user {
  margin-left: auto;
  background: linear-gradient(135deg, #0f766e, #115e59);
  color: #f8fafc;
}

.message-user .bubble-label {
  color: rgba(240, 253, 250, 0.86);
}

.message-assistant {
  background: rgba(255, 255, 255, 0.9);
  color: #111827;
  border: 1px solid rgba(148, 163, 184, 0.22);
}

.message-assistant .bubble-label {
  color: #0f766e;
}

.message-error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid rgba(239, 68, 68, 0.18);
}

.message-error .bubble-label {
  color: #b91c1c;
}

.trace-card {
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(148, 163, 184, 0.22);
}

.trace-card h3 {
  margin-bottom: 8px;
  font-size: 16px;
}

.trace-thought {
  border-left: 4px solid #f59e0b;
}

.trace-thought .trace-stage {
  color: #b45309;
}

.trace-action {
  border-left: 4px solid #0ea5e9;
}

.trace-action .trace-stage {
  color: #0369a1;
}

.trace-observation {
  border-left: 4px solid #10b981;
}

.trace-observation .trace-stage {
  color: #047857;
}

.streaming-indicator {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  color: #5b6475;
}

.composer {
  display: grid;
  gap: 12px;
}

@media (max-width: 640px) {
  .example-row {
    grid-template-columns: 1fr;
  }

  .message-bubble,
  .trace-card {
    max-width: 100%;
  }
}
</style>
