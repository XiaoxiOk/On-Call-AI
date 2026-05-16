export interface HealthResponse {
  status: string
}

export interface PhaseStatusResponse {
  phase: string
  message: string
}

export interface SearchResult {
  id: string
  title: string
  snippet: string
  score: number
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
}

export type ChatRole = 'user' | 'assistant'

export interface ChatHistoryMessage {
  role: ChatRole
  content: string
}

export interface ChatRequest {
  message: string
  history: ChatHistoryMessage[]
}

export type AgentTraceStage = 'thought' | 'action' | 'observation'

export interface AgentTracePayload {
  id: string
  stage: AgentTraceStage
  title: string
  content: string
}

export interface AgentTokenPayload {
  delta: string
}

export interface AgentMessagePayload {
  content: string
}

export interface AgentErrorPayload {
  message: string
}

export interface AgentDonePayload {
  final_text: string
}
