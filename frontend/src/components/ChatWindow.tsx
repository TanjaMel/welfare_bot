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
};

const API_BASE = typeof window !== "undefined" && window.location.hostname !== "localhost"
  ? "/api/v1"
  : "http://127.0.0.1:8000/api/v1";

function formatTime(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function getRiskClass(riskLevel?: string | null): string {
  if (!riskLevel) return "";
  const normalized = riskLevel.toLowerCase();
  if (normalized === "low") return "message-risk-low";
  if (normalized === "medium") return "message-risk-medium";
  if (normalized === "high" || normalized === "critical") return "message-risk-high";
  return "";
}

export default function ChatWindow({
  title = "Welfare Bot Chat",
  subtitle = "AI-powered welfare assistant",
  messages,
  onSend,
  loading,
  error,
  language = "fi",
}: Props) {
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
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
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.role === "assistant" && lastMessage.content) {
      void speakText(lastMessage.content);
    }
  }, [messages, voiceEnabled]);

  async function speakText(text: string) {
    if (!text.trim()) return;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsSpeaking(true);
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
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      audio.onended = () => { setIsSpeaking(false); URL.revokeObjectURL(audioUrl); };
      audio.onerror = () => { setIsSpeaking(false); URL.revokeObjectURL(audioUrl); };
      await audio.play();
    } catch {
      setIsSpeaking(false);
    }
  }

  function stopSpeaking() {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    setIsSpeaking(false);
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
      mediaRecorder.start(100); // collect data every 100ms
    
      setIsRecording(true);
    } catch {
      setRecordingError("Microphone access denied. Please allow microphone access.");
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && isRecording) {
      // Request any buffered data before stopping
      mediaRecorderRef.current.requestData();
      // Small delay to ensure data is collected
      setTimeout(() => {
        if (mediaRecorderRef.current) {
          mediaRecorderRef.current.stop();
        }
        setIsRecording(false);
      }, 300);
    }
  }

  async function transcribeAudio(audioBlob: Blob) {
    try {
      const token = localStorage.getItem("access_token");
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("language", language);
      const response = await fetch(`${API_BASE}/voice/transcribe`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!response.ok) throw new Error("Transcription failed");
      const data = await response.json() as { text?: string };
      const text = data.text?.trim();
      if (text) {
        await onSend(text);
      } else {
        setRecordingError("Could not understand the audio. Please try again.");
      }
    } catch {
      setRecordingError("Transcription failed. Please try again or type your message.");
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
      // parent handles error
    }
  }

  return (
    <div className="chat-card">
      <div className="chat-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="chat-title">{title}</h1>
            <p className="chat-subtitle">{subtitle}</p>
          </div>
          <button
            onClick={() => { setVoiceEnabled(!voiceEnabled); stopSpeaking(); }}
            title={voiceEnabled ? "Turn off voice" : "Turn on voice"}
            style={{
              background: voiceEnabled ? "#3b82f6" : "#475569",
              border: "none",
              borderRadius: "8px",
              color: "white",
              cursor: "pointer",
              fontSize: "14px",
              padding: "6px 12px",
              marginTop: "4px",
            }}
          >
            {voiceEnabled ? "Voice ON" : "Voice OFF"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {recordingError && <div className="error-box">{recordingError}</div>}

      <div className="messages-box">
        {!hasMessages ? (
          <div className="empty-state">No messages yet</div>
        ) : (
          messages.map((message) => {
            const isUser = message.role === "user";
            const riskClass = getRiskClass(message.risk_level);
            return (
              <div key={message.id} className={`message-row ${isUser ? "user" : "assistant"}`}>
                <div className={`message-bubble ${isUser ? "user" : "assistant"} ${riskClass}`}>
                  {message.risk_level && isUser && (
                    <div className={`message-risk-pill ${riskClass}`}>
                      Risk: {message.risk_level}
                      {typeof message.risk_score === "number" ? ` (${message.risk_score})` : ""}
                    </div>
                  )}
                  <div className="message-content">
                    {message.content || (!isUser ? "..." : "")}
                  </div>
                  {!isUser && message.content && voiceEnabled && (
                    <button
                      onClick={() => isSpeaking ? stopSpeaking() : void speakText(message.content)}
                      style={{
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        fontSize: "12px",
                        color: "#94a3b8",
                        padding: "2px 4px",
                        marginTop: "4px",
                      }}
                    >
                      {isSpeaking ? "Stop" : "Play"}
                    </button>
                  )}
                  <div className="message-meta">
                    <span className="message-role">{isUser ? "You" : "Welfare Bot"}</span>
                    <span className="message-time">{formatTime(message.created_at)}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {loading && <div className="loading-box">Welfare Bot is typing...</div>}
      {isSpeaking && <div className="loading-box">Speaking...</div>}

      <form className="input-area" onSubmit={handleSubmit}>
        <textarea
          placeholder="Write a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading || isRecording}
        />
        {/* Microphone button - press once to start, press again to stop */}
        <button
          type="button"
          onClick={() => isRecording ? stopRecording() : void startRecording()}
          disabled={loading}
          title={isRecording ? "Press to stop recording" : "Press to start recording"}
          style={{
            background: isRecording ? "#dc2626" : "#475569",
            border: isRecording ? "3px solid #fca5a5" : "3px solid transparent",
            borderRadius: "8px",
            color: "white",
            cursor: "pointer",
            fontSize: "14px",
            padding: "8px 14px",
            transition: "all 0.2s",
            userSelect: "none",
            animation: isRecording ? "pulse 1s infinite" : "none",
          }}
        >
          {isRecording ? "Stop recording" : "Speak"}
        </button>
     
        <button
          className="send-button"
          type="submit"
          disabled={loading || !input.trim() || isRecording}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}