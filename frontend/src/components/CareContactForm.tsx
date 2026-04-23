import { useState, useEffect } from "react";
import {
  getCareContacts,
  createCareContact,
  deleteCareContact,
  type CareContact,
  type CareContactCreate,
} from "../api";

type Props = {
  userId: number;
};

export default function CareContactForm({ userId }: Props) {
  const [contacts, setContacts] = useState<CareContact[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<CareContactCreate>({
    user_id: userId,
    name: "",
    relationship_type: "family",
    phone_number: "",
    email: "",
    preferred_notification_method: "email",
    is_primary: true,
  });

  useEffect(() => {
    void loadContacts();
  }, [userId]);

  async function loadContacts() {
    try {
      const data = await getCareContacts(userId);
      setContacts(data);
    } catch {
      setContacts([]);
    }
  }

  async function handleSave() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await createCareContact({ ...form, user_id: userId });
      setShowForm(false);
      setForm({
        user_id: userId,
        name: "",
        relationship_type: "family",
        phone_number: "",
        email: "",
        preferred_notification_method: "email",
        is_primary: true,
      });
      await loadContacts();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteCareContact(id);
      await loadContacts();
    } catch {
      // ignore
    }
  }

  return (
    <div className="sidebar-card">
      <div className="card-title">Care contact</div>

      {contacts.length === 0 && !showForm && (
        <div className="muted-text" style={{ marginBottom: "8px" }}>
          No care contact added yet
        </div>
      )}

      {contacts.map((c) => (
        <div key={c.id} style={{ marginBottom: "8px", fontSize: "13px" }}>
          <div><strong>{c.name}</strong> — {c.relationship_type}</div>
          {c.email && <div style={{ color: "#94a3b8" }}>{c.email}</div>}
          {c.phone_number && <div style={{ color: "#94a3b8" }}>{c.phone_number}</div>}
          <button
            onClick={() => void handleDelete(c.id)}
            style={{
              background: "transparent",
              border: "none",
              color: "#ef4444",
              cursor: "pointer",
              fontSize: "12px",
              padding: "2px 0",
            }}
          >
            Remove
          </button>
        </div>
      ))}

      {showForm && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "8px" }}>
          <input
            placeholder="Name *"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            style={inputStyle}
          />
          <select
            value={form.relationship_type}
            onChange={(e) => setForm({ ...form, relationship_type: e.target.value })}
            style={inputStyle}
          >
            <option value="family">Family</option>
            <option value="spouse">Spouse</option>
            <option value="child">Child</option>
            <option value="friend">Friend</option>
            <option value="care_worker">Care worker</option>
            <option value="neighbor">Neighbor</option>
          </select>
          <input
            placeholder="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            style={inputStyle}
          />
          <input
            placeholder="Phone number"
            value={form.phone_number}
            onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
            style={inputStyle}
          />
          <select
            value={form.preferred_notification_method}
            onChange={(e) => setForm({ ...form, preferred_notification_method: e.target.value })}
            style={inputStyle}
          >
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="call">Phone call</option>
          </select>
          <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
            <button
              onClick={() => void handleSave()}
              disabled={saving || !form.name.trim()}
              style={{
                flex: 1,
                background: "#3b82f6",
                border: "none",
                borderRadius: "6px",
                color: "white",
                cursor: "pointer",
                padding: "6px",
                fontSize: "13px",
              }}
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              style={{
                flex: 1,
                background: "#475569",
                border: "none",
                borderRadius: "6px",
                color: "white",
                cursor: "pointer",
                padding: "6px",
                fontSize: "13px",
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {!showForm && (
        <button
          onClick={() => setShowForm(true)}
          style={{
            marginTop: "8px",
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "6px",
            color: "#94a3b8",
            cursor: "pointer",
            padding: "6px 10px",
            fontSize: "13px",
            width: "100%",
          }}
        >
          + Add care contact
        </button>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: "6px",
  color: "white",
  fontSize: "13px",
  padding: "6px 8px",
  width: "100%",
  boxSizing: "border-box",
};