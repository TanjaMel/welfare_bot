export type User = {
  id: number;
  first_name: string;
  last_name: string | null;
  phone_number: string;
  email?: string | null;
  role?: string;
  language: string;
  timezone?: string | null;
  notes?: string | null;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type UserLogin = {
  email: string;
  password: string;
};

export type UserRegister = {
  first_name: string;
  last_name: string;
  phone_number: string;
  language: string;
  email: string;
  password: string;
  role?: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type CreateUserRequest = {
  first_name: string;
  last_name?: string | null;
  phone_number: string;
  language?: string;
};

export type ConversationMessage = {
  id: number;
  user_id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  message_type?: string;
  risk_level?: string | null;
  risk_score?: number | null;
  risk_category?: string | null;
  created_at: string;
};

export type RiskAnalysis = {
  id: number;
  user_id: number;
  daily_checkin_id?: number | null;
  conversation_message_id?: number | null;
  category: string;
  risk_level: string;
  risk_score: number;
  reason?: string | null;
  suggested_action?: string | null;
  follow_up_question?: string | null;
  signals_json?: string[];
  reasons_json?: string[];
  needs_family_notification?: boolean;
  should_alert_family?: boolean;
  model_version?: string | null;
  created_at?: string;
};

export type SendMessageRequest = {
  user_id: number;
  message: string;
  language?: string;
};

export type SendMessageResponse = {
  reply: string;
  risk_analysis?: RiskAnalysis | null;
  notifications?: unknown[];
  mode?: string;
};