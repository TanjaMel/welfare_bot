import type {
  ConversationMessage,
  CreateUserRequest,
  RiskAnalysis,
  SendMessageRequest,
  SendMessageResponse,
  User,
} from "./types";

const API_BASE = "http://127.0.0.1:8000/api/v1";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP error ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function getUsers(): Promise<User[]> {
  const response = await fetch(`${API_BASE}/users/`);
  return handleResponse<User[]>(response);
}

export async function createUser(payload: CreateUserRequest): Promise<User> {
  const response = await fetch(`${API_BASE}/users/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<User>(response);
}

// FIXED: removed extra "user/" segment
export async function getMessages(userId: number): Promise<ConversationMessage[]> {
  const response = await fetch(`${API_BASE}/conversations/${userId}/messages`);
  return handleResponse<ConversationMessage[]>(response);
}

// FIXED: removed extra "user/" segment
export async function deleteMessages(userId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/conversations/${userId}/messages`, {
    method: "DELETE",
  });
  await handleResponse<void>(response);
}

export async function getUserRiskAnalysis(userId: number): Promise<RiskAnalysis[]> {
  const response = await fetch(`${API_BASE}/conversations/${userId}/risk-analysis`);
  return handleResponse<RiskAnalysis[]>(response);
}

export async function sendMessage(payload: SendMessageRequest): Promise<SendMessageResponse> {
  const response = await fetch(`${API_BASE}/conversations/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<SendMessageResponse>(response);
}

// Backend does not stream yet — falls back to regular sendMessage
// onChunk is called once with the full reply
export async function sendMessageStream(
  payload: SendMessageRequest,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const result = await sendMessage(payload);
  if (result.reply) {
    onChunk(result.reply);
  }
}

export type { User, RiskAnalysis };