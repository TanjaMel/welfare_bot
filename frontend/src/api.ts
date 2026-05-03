import type {
  ConversationMessage,
  CreateUserRequest,
  RiskAnalysis,
  SendMessageRequest,
  SendMessageResponse,
  TokenResponse,
  User,
  UserLogin,
  UserRegister,
  WellbeingSummary,
  WellbeingTrendPoint,
  WellbeingInsight,
} from "./types";


const API_BASE = typeof window !== "undefined" && window.location.hostname !== "localhost"
  ? "/api/v1"  // on Railway, same domain — use relative URL
  : "http://127.0.0.1:8000/api/v1";  // local dev
function getToken(): string | null {
  return localStorage.getItem("access_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    if (response.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("current_user");
      window.location.reload();
    }
    throw new Error(text || `HTTP error ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(payload: UserLogin): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<TokenResponse>(response);
}

export async function register(payload: UserRegister): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<TokenResponse>(response);
}

export async function getMe(): Promise<User> {
  const response = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
  return handleResponse<User>(response);
}

export async function getUsers(): Promise<User[]> {
  const response = await fetch(`${API_BASE}/users/`, { headers: authHeaders() });
  return handleResponse<User[]>(response);
}

export async function createUser(payload: CreateUserRequest): Promise<User> {
  const response = await fetch(`${API_BASE}/users/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<User>(response);
}

export async function getMessages(userId: number): Promise<ConversationMessage[]> {
  const response = await fetch(`${API_BASE}/conversations/${userId}/messages`, {
    headers: authHeaders(),
  });
  return handleResponse<ConversationMessage[]>(response);
}

export async function deleteMessages(userId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/conversations/${userId}/messages`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  await handleResponse<void>(response);
}

export async function getUserRiskAnalysis(userId: number): Promise<RiskAnalysis[]> {
  const response = await fetch(`${API_BASE}/conversations/${userId}/risk-analysis`, {
    headers: authHeaders(),
  });
  return handleResponse<RiskAnalysis[]>(response);
}

export async function sendMessage(payload: SendMessageRequest): Promise<SendMessageResponse> {
  const response = await fetch(`${API_BASE}/conversations/message`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<SendMessageResponse>(response);
}

export async function sendMessageStream(
  payload: SendMessageRequest,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const result = await sendMessage(payload);
  if (result.reply) onChunk(result.reply);
}

export function logout(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("current_user");
  window.location.reload();
}
export async function startConversation(
  userId: number,
): Promise<ConversationMessage> {
  const response = await fetch(
    `${API_BASE}/conversations/start?user_id=${userId}&language=fi`,
    {
      method: "POST",
      headers: authHeaders(),
    },
  );
  return handleResponse<ConversationMessage>(response);
}
export interface CareContact {
  id: number;
  user_id: number;
  name: string;
  relationship_type: string;
  phone_number?: string;
  email?: string;
  preferred_notification_method: string;
  is_primary: boolean;
  notes?: string;
  created_at: string;
}

export interface CareContactCreate {
  user_id: number;
  name: string;
  relationship_type: string;
  phone_number?: string;
  email?: string;
  preferred_notification_method?: string;
  is_primary?: boolean;
  notes?: string;
}

export async function getCareContacts(userId: number): Promise<CareContact[]> {
  const response = await fetch(`${API_BASE}/care-contacts/user/${userId}`, {
    headers: authHeaders(),
  });
  return handleResponse<CareContact[]>(response);
}

export async function createCareContact(payload: CareContactCreate): Promise<CareContact> {
  const response = await fetch(`${API_BASE}/care-contacts/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<CareContact>(response);
}

export async function deleteCareContact(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/care-contacts/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleResponse<void>(response);
}
export type { User, RiskAnalysis };

export async function getWellbeingSummary(userId: number): Promise<WellbeingSummary> {
  const response = await fetch(`${API_BASE}/wellbeing/summary/${userId}`, {
    headers: authHeaders(),
  });
  return handleResponse<WellbeingSummary>(response);
}

export async function getWellbeingTrends(userId: number, days: number = 7): Promise<WellbeingTrendPoint[]> {
  const response = await fetch(`${API_BASE}/wellbeing/trends/${userId}?days=${days}`, {
    headers: authHeaders(),
  });
  // The endpoint returns { days, points, trend_message } — extract points
  const data = await handleResponse<{ points: WellbeingTrendPoint[] }>(response);
  return data.points;
}

export async function getWellbeingInsights(userId: number): Promise<WellbeingInsight[]> {
  const response = await fetch(`${API_BASE}/wellbeing/insights/${userId}`, {
    headers: authHeaders(),
  });
  // The endpoint returns { insights, summary } — extract insights
  const data = await handleResponse<{ insights: WellbeingInsight[] }>(response);
  return data.insights;
}

export async function requestPasswordReset(email: string): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  return handleResponse<void>(response);
}