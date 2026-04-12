import type {
  ConversationMessage,
  CreateUserRequest,
  CreateUserResponse,
  SendMessageRequest,
} from "./types";

const API_BASE = "http://127.0.0.1:8000/api/v1";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function createUser(
  payload: CreateUserRequest,
): Promise<CreateUserResponse> {
  const response = await fetch(`${API_BASE}/users/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse<CreateUserResponse>(response);
}

export async function getMessages(
  userId: number,
): Promise<ConversationMessage[]> {
  const response = await fetch(`${API_BASE}/conversations/${userId}/messages`);
  return handleResponse<ConversationMessage[]>(response);
}

export async function sendMessageStream(
  payload: SendMessageRequest,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/conversations/message/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Streaming response body is missing");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      if (chunk) {
        onChunk(chunk);
      }
    }

    const tail = decoder.decode();
    if (tail) {
      onChunk(tail);
    }
  } finally {
    reader.releaseLock();
  }
}