const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL
}

export function resolveApiUrl(path: string): string {
  return new URL(path, getApiBaseUrl()).toString()
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
  })

  if (!response.ok) {
    const contentType = response.headers.get('content-type') ?? ''
    let detail = ''

    if (contentType.includes('application/json')) {
      const body = (await response.json()) as {
        detail?: string
        message?: string
      }
      detail = body.detail ?? body.message ?? JSON.stringify(body)
    } else {
      detail = await response.text()
    }

    throw new ApiError(response.status, detail || 'Request failed.')
  }

  return (await response.json()) as T
}
