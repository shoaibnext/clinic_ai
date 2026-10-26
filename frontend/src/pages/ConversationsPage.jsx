import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const STATUS_COLORS = {
  ai_active: "badge-confirmed",
  human_requested: "badge-pending",
  human_active: "badge-completed",
  resolved: "badge-cancelled",
};

export default function ConversationsPage() {
  const [conversations, setConversations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [patients, setPatients] = useState({});

  const load = async () => {
    try {
      const data = await api.getConversations();
      setConversations(data);
      const patientIds = [...new Set(data.map((c) => c.patient_id))];
      const patientData = await Promise.all(patientIds.map((id) => api.getPatient(id).catch(() => null)));
      const map = {};
      patientData.forEach((p, i) => { if (p) map[patientIds[i]] = p; });
      setPatients(map);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const selectConversation = async (conv) => {
    setSelected(conv);
    try {
      const detail = await api.getConversation(conv.id);
      setMessages(detail.messages || []);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleStatusChange = async (conv, newStatus) => {
    try {
      await api.updateConversation(conv.id, { status: newStatus });
      await load();
      if (selected?.id === conv.id) {
        setSelected({ ...conv, status: newStatus });
      }
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return <div className="container">Loading...</div>;

  return (
    <div className="container">
      <header>
        <h1>Conversations</h1>
        {error && <div className="error">{error}</div>}
      </header>

      <div className="conversations-layout">
        <section className="card conversation-list">
          <h2>All Conversations ({conversations.length})</h2>
          {conversations.length === 0 ? (
            <p className="empty">No conversations yet</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Status</th>
                  <th>Channel</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {conversations.map((c) => (
                  <tr
                    key={c.id}
                    className={selected?.id === c.id ? "selected-row" : ""}
                    onClick={() => selectConversation(c)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{patients[c.patient_id]?.full_name || patients[c.patient_id]?.phone_number || `#${c.patient_id}`}</td>
                    <td><span className={`badge ${STATUS_COLORS[c.status] || ""}`}>{c.status}</span></td>
                    <td>{c.channel}</td>
                    <td>{new Date(c.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card conversation-detail">
          {selected ? (
            <>
              <div className="conversation-header">
                <h2>Conversation #{selected.id}</h2>
                <select
                  value={selected.status}
                  onChange={(e) => handleStatusChange(selected, e.target.value)}
                >
                  <option value="ai_active">AI Active</option>
                  <option value="human_requested">Human Requested</option>
                  <option value="human_active">Human Active</option>
                  <option value="resolved">Resolved</option>
                </select>
              </div>
              <div className="chat-messages">
                {messages.length === 0 ? (
                  <p className="empty">No messages in this conversation</p>
                ) : (
                  messages.map((m) => (
                    <div key={m.id} className={`chat-bubble ${m.direction === "out" ? "ai" : "patient"}`}>
                      <div className="chat-meta">
                        {m.direction === "out" ? "AI" : "Patient"} &middot; {new Date(m.created_at).toLocaleTimeString()}
                      </div>
                      <div className="chat-text">{m.body}</div>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <p>Select a conversation to view messages</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
