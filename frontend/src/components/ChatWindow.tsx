import { useEffect, useMemo, useRef, useState } from "react";
import type { ConversationMessage } from "../types";

type Props = {
  title?: string;
  subtitle?: string;
  messages: ConversationMessage[];
  onSend: (text: string) => void | Promise<void>;
  loading: boolean;
  error: string | null;
  language?: string;
  userInitial?: string;
};

const API_BASE = "/api/v1";

function formatTime(value?: string | null): string {
  if (!value) return "";
  const normalized = value.endsWith("Z") || value.includes("+") ? value : value + "Z";
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function getRiskClass(riskLevel?: string | null): string {
  if (!riskLevel) return "";
  const n = riskLevel.toLowerCase();
  if (n === "low") return "message-risk-low";
  if (n === "medium") return "message-risk-medium";
  if (n === "high" || n === "critical") return "message-risk-high";
  return "";
}

function BotMark() {
  return (
    <div className="bot-mark" aria-hidden="true">
      <svg viewBox="0 0 64 64" fill="none">
        <defs>
          <linearGradient id="chatLogoGradient" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#4F7DF3" />
            <stop offset="100%" stopColor="#6A8BFF" />
          </linearGradient>
        </defs>
        <path
          d="M32 6L50 16C53.105 17.725 55 21.001 55 24.55V39.45C55 42.999 53.105 46.275 50 48L32 58L14 48C10.895 46.275 9 42.999 9 39.45V24.55C9 21.001 10.895 17.725 14 16L32 6Z"
          fill="url(#chatLogoGradient)"
        />
        <circle cx="32" cy="22" r="6.4" fill="white" />
        <path
          d="M21.2 35.2C21.2 33.433 22.633 32 24.4 32H39.2C40.967 32 42.4 33.433 42.4 35.2L34.3 44.4C33.037 45.833 30.814 45.871 29.503 44.483L21.2 35.2Z"
          fill="white"
        />
        <path
          d="M27.5 36.3L31.4 40.1L40.1 30.8"
          stroke="#3E6FF2"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

export default function ChatWindow({
  title = "Welfare Bot Chat",
  subtitle = "Reliable conversational support for everyday well-being",
  messages,
  onSend,
  loading,
  error,
  language = "auto",
  userInitial = "U",
}: Props) {
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState<number | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [recordingError, setRecordingError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const prevMessagesLengthRef = useRef(0);

  const hasMessages = useMemo(() => messages.length > 0, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!voiceEnabled) return;
    if (messages.length <= prevMessagesLengthRef.current) {
      prevMessagesLengthRef.current = messages.length;
      return;
    }
    prevMessagesLengthRef.current = messages.length;
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && last.content) {
      void speakText(last.content, last.id);
    }
  }, [messages, voiceEnabled]);

  function stopSpeaking() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
    }
    setIsSpeaking(false);
    setSpeakingMessageId(null);
  }

  async function speakText(text: string, messageId?: number) {
    if (!text.trim()) return;
    stopSpeaking();
    setIsSpeaking(true);
    setSpeakingMessageId(messageId ?? null);

    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch(`${API_BASE}/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text, language }),
      });

      if (!response.ok) throw new Error("TTS failed");

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio();
      audio.src = audioUrl;
      audio.preload = "auto";

      audioRef.current = audio;
      audio.onended = () => {
        setIsSpeaking(false);
        setSpeakingMessageId(null);
        URL.revokeObjectURL(audioUrl);
      };
      audio.onerror = () => {
        setIsSpeaking(false);
        setSpeakingMessageId(null);
        URL.revokeObjectURL(audioUrl);
      };

      audio.load();
      try {
        await audio.play();
      } catch {
        // Autoplay blocked — user needs to tap Play manually
        setIsSpeaking(false);
        setSpeakingMessageId(null);
      }
    } catch {
      setIsSpeaking(false);
      setSpeakingMessageId(null);
    }
  }

  async function startRecording() {
    setRecordingError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/ogg";
      const mediaRecorder = new MediaRecorder(stream, { mimeType });

      audioChunksRef.current = [];
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        await transcribeAudio(audioBlob);
      };

      mediaRecorder.start(100);
      setIsRecording(true);
    } catch {
      setRecordingError("Microphone access denied.");
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.requestData();
      setTimeout(() => {
        if (mediaRecorderRef.current) mediaRecorderRef.current.stop();
        setIsRecording(false);
      }, 300);
    }
  }

  async function transcribeAudio(audioBlob: Blob) {
    try {
      const token = localStorage.getItem("access_token");
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("language", language === "auto" ? "fi" : language);

      const response = await fetch(`${API_BASE}/voice/transcribe`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!response.ok) throw new Error("Transcription failed");

      const data = (await response.json()) as { text?: string };
      const text = data.text?.trim();

      if (text) {
        await onSend(text);
      } else {
        setRecordingError("Could not understand. Please try again.");
      }
    } catch {
      setRecordingError("Transcription failed. Please type instead.");
    }
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    try {
      await onSend(text);
      setInput("");
    } catch {
      // handled upstream
    }
  }

  return (
    <div className="chat-card">
      <div className="chat-header">
        <div>
          <h1 className="chat-title">{title}</h1>
          <p className="chat-subtitle">{subtitle}</p>
        </div>
        <button
          className={`voice-toggle-btn ${voiceEnabled ? "active" : ""}`}
          onClick={() => { setVoiceEnabled(!voiceEnabled); stopSpeaking(); }}
          type="button"
        >
          <span className={`voice-dot ${voiceEnabled ? "active" : ""}`} />
          Voice mode {voiceEnabled ? "On" : "Off"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {recordingError && <div className="error-box">{recordingError}</div>}

      <div className="messages-box">
        {!hasMessages ? (
          <div className="empty-state">
            <div className="empty-state-mark"><BotMark /></div>
            <h3>No messages yet</h3>
            <p>Start the conversation below.</p>
          </div>
        ) : (
          messages.map((message) => {
            const isUser = message.role === "user";
            const riskClass = getRiskClass(message.risk_level);
            const isThisMessageSpeaking = speakingMessageId === message.id && isSpeaking;

            return (
              <div key={message.id} className={`message-row ${isUser ? "user" : "assistant"}`}>
                {!isUser && <div className="msg-avatar bot"><BotMark /></div>}

                <div className={`message-bubble ${isUser ? "user" : "assistant"} ${riskClass}`}>


                  <div className="message-content">{message.content || (!isUser ? "..." : "")}</div>

                  {!isUser && message.content && voiceEnabled && (
                    <button
                      className="play-btn"
                      type="button"
                      onClick={() =>
                        isThisMessageSpeaking
                          ? stopSpeaking()
                          : void speakText(message.content, message.id)
                      }
                    >
                      {isThisMessageSpeaking ? "Stop audio" : "Play audio"}
                    </button>
                  )}

                  <div className="message-meta">
                    <span>{isUser ? "You" : "Welfare Bot"}</span>
                    <span>{formatTime(message.created_at)}</span>
                  </div>
                </div>

                {isUser && <div className="msg-avatar user-av">{userInitial}</div>}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {loading && <div className="loading-box">Welfare Bot is responding...</div>}
      {isSpeaking && <div className="loading-box">Audio playback in progress...</div>}

      <form className="input-area" onSubmit={handleSubmit}>
        <button
          type="button"
          className={`mic-btn ${isRecording ? "recording" : ""}`}
          onClick={() => (isRecording ? stopRecording() : void startRecording())}
          disabled={loading}
          title={isRecording ? "Stop recording" : "Start voice input"}
        >
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M12 15C10.3431 15 9 13.6569 9 12V6C9 4.34315 10.3431 3 12 3C13.6569 3 15 4.34315 15 6V12C15 13.6569 13.6569 15 12 15Z" stroke="currentColor" strokeWidth="1.8" />
            <path d="M18 11.5C18 14.8137 15.3137 17.5 12 17.5C8.68629 17.5 6 14.8137 6 11.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M12 17.5V21" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          <span className="mic-label">{isRecording ? "Recording" : "Voice"}</span>
        </button>

        <div className="input-wrapper">
          <textarea
            placeholder="Write a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading || isRecording}
            rows={1}
          />
        </div>

        <button className="send-button" type="submit" disabled={loading || !input.trim() || isRecording}>
          Send
        </button>
      </form>

      <div className="input-privacy">Your conversations are private and secure</div>
    </div>
  );
}
