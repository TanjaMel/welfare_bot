import { useState } from "react";

type Props = {
  onSend: (text: string) => Promise<void>;
  disabled?: boolean;
};

export default function MessageInput({
  onSend,
  disabled = false,
}: Props) {
  const [text, setText] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const trimmed = text.trim();
    if (!trimmed) return;

    await onSend(trimmed);
    setText("");
  }

  return (
    <form className="message-input-form" onSubmit={handleSubmit}>
      <textarea
        className="message-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Write a message..."
        rows={3}
        disabled={disabled}
      />
      <button
        className="send-button"
        type="submit"
        disabled={disabled || !text.trim()}
      >
        {disabled ? "Sending..." : "Send"}
      </button>
    </form>
  );
}