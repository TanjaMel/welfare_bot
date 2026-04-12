export type CreateUserRequest = {
  first_name: string;
  last_name: string;
  phone_number: string;
  language: string;
};

export type CreateUserResponse = {
  id: number;
  first_name: string;
  last_name: string;
  phone_number: string;
  language: string;
};

export type ConversationMessage = {
  id: number;
  role: string;
  content: string;
  created_at?: string;
};

export type SendMessageRequest = {
  user_id: number;
  message: string;
};

export type SendMessageResponse = {
  reply: string;
};
