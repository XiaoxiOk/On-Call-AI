import { resolveApiUrl } from './http'

export interface SseEvent {
  event: string
  data: string
}

function parseEventBlock(block: string): SseEvent | null {
  const lines = block.split(/\r?\n/)
  let event = 'message'
  const dataLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim() || 'message'
      continue
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  return {
    event,
    data: dataLines.join('\n'),
  }
}

export async function streamSse(
  path: string,
  init: RequestInit,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const response = await fetch(resolveApiUrl(path), {
    ...init,
    headers: {
      Accept: 'text/event-stream',
      ...(init.headers ?? {}),
    },
  })

  if (!response.ok || !response.body) {
    throw new Error('Unable to open SSE stream.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()

    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const event = parseEventBlock(chunk.trim())
      if (event) {
        onEvent(event)
      }
    }
  }

  const finalEvent = parseEventBlock(buffer.trim())
  if (finalEvent) {
    onEvent(finalEvent)
  }
}
