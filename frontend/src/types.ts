export type ConversationMessage = {
  id: number;
  role: string;
  content: string;
  created_at?: string | null;
  risk_level?: string | null;
  risk_score?: number | null;
  risk_category?: string | null;
};

export type CreateUserRequest = {
  first_name: string;
  last_name: string;
  phone_number: string;
  language: string;
};


export type SendMessageRequest = {
  user_id: number;
  message: string;
  language?: string;
};