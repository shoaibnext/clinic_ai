import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function KnowledgePage() {
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showKbForm, setShowKbForm] = useState(false);
  const [showDocForm, setShowDocForm] = useState(false);
  const [kbForm, setKbForm] = useState({ name: "", description: "" });
  const [docForm, setDocForm] = useState({ knowledge_base_id: "", filename: "", content: "" });
  const [selectedKb, setSelectedKb] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);

  const load = async () => {
    try {
      const [kb, docs] = await Promise.all([
        api.getKnowledgeBases(),
        api.getDocuments(),
      ]);
      setKnowledgeBases(kb);
      setDocuments(docs);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreateKb = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.createKnowledgeBase(kbForm);
      setKbForm({ name: "", description: "" });
      setShowKbForm(false);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleCreateDoc = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.createDocument({
        knowledge_base_id: Number(docForm.knowledge_base_id),
        filename: docForm.filename,
        content: docForm.content,
      });
      setDocForm({ knowledge_base_id: "", filename: "", content: "" });
      setShowDocForm(false);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDeleteDoc = async (id) => {
    if (!confirm("Delete this document?")) return;
    try {
      await api.deleteDocument(id);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    try {
      const result = await api.searchKnowledge(searchQuery);
      setSearchResults(result);
    } catch (e) {
      setError(e.message);
    }
  };

  const filteredDocs = selectedKb
    ? documents.filter((d) => d.knowledge_base_id === selectedKb)
    : documents;

  if (loading) return <div className="container">Loading...</div>;

  return (
    <div className="container">
      <header>
        <div className="header-row">
          <h1>Knowledge Base</h1>
          <div className="header-actions">
            <button onClick={() => { setShowKbForm(!showKbForm); setShowDocForm(false); }}>
              {showKbForm ? "Cancel" : "+ New Knowledge Base"}
            </button>
            <button onClick={() => { setShowDocForm(!showDocForm); setShowKbForm(false); }}>
              {showDocForm ? "Cancel" : "+ Add Document"}
            </button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
      </header>

      <div className="knowledge-layout">
        <section className="card kb-sidebar">
          <h2>Knowledge Bases</h2>
          <div
            className={`kb-item ${selectedKb === null ? "active" : ""}`}
            onClick={() => setSelectedKb(null)}
          >
            All Documents ({documents.length})
          </div>
          {knowledgeBases.map((kb) => (
            <div
              key={kb.id}
              className={`kb-item ${selectedKb === kb.id ? "active" : ""}`}
              onClick={() => setSelectedKb(kb.id)}
            >
              <strong>{kb.name}</strong>
              {kb.description && <p>{kb.description}</p>}
            </div>
          ))}
        </section>

        <section className="card kb-main">
          {showKbForm && (
            <form onSubmit={handleCreateKb} className="form-card">
              <h2>New Knowledge Base</h2>
              <div className="form-grid">
                <div className="form-group">
                  <label>Name</label>
                  <input
                    value={kbForm.name}
                    onChange={(e) => setKbForm({ ...kbForm, name: e.target.value })}
                    placeholder="Clinic FAQ"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <input
                    value={kbForm.description}
                    onChange={(e) => setKbForm({ ...kbForm, description: e.target.value })}
                    placeholder="Common questions and answers"
                  />
                </div>
                <div className="form-actions">
                  <button type="submit">Create</button>
                </div>
              </div>
            </form>
          )}

          {showDocForm && (
            <form onSubmit={handleCreateDoc} className="form-card">
              <h2>Add Document</h2>
              <div className="form-grid">
                <div className="form-group">
                  <label>Knowledge Base</label>
                  <select
                    value={docForm.knowledge_base_id}
                    onChange={(e) => setDocForm({ ...docForm, knowledge_base_id: e.target.value })}
                    required
                  >
                    <option value="">Select knowledge base</option>
                    {knowledgeBases.map((kb) => (
                      <option key={kb.id} value={kb.id}>{kb.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Filename</label>
                  <input
                    value={docForm.filename}
                    onChange={(e) => setDocForm({ ...docForm, filename: e.target.value })}
                    placeholder="clinic_info.txt"
                    required
                  />
                </div>
                <div className="form-group full-width">
                  <label>Content</label>
                  <textarea
                    value={docForm.content}
                    onChange={(e) => setDocForm({ ...docForm, content: e.target.value })}
                    placeholder="Paste your clinic information, FAQ, policies, etc."
                    rows={8}
                    required
                  />
                </div>
                <div className="form-actions">
                  <button type="submit">Add Document</button>
                </div>
              </div>
            </form>
          )}

          <div className="search-bar">
            <form onSubmit={handleSearch} className="row">
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search knowledge base..."
              />
              <button type="submit">Search</button>
            </form>
          </div>

          {searchResults && (
            <div className="search-results">
              <h3>Search Results for "{searchResults.query}"</h3>
              {searchResults.results.length === 0 ? (
                <p className="empty">No results found</p>
              ) : (
                searchResults.results.map((r, i) => (
                  <div key={i} className="result-card">
                    <div className="result-meta">
                      Document #{r.document_id} &middot; Chunk {r.chunk_index} &middot; Score: {r.score.toFixed(3)}
                    </div>
                    <div className="result-content">{r.content}</div>
                  </div>
                ))
              )}
            </div>
          )}

          <h2>Documents ({filteredDocs.length})</h2>
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Knowledge Base</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.map((d) => (
                <tr key={d.id}>
                  <td>{d.filename}</td>
                  <td>KB #{d.knowledge_base_id}</td>
                  <td><span className={`badge badge-${d.status === "processed" ? "confirmed" : d.status === "failed" ? "cancelled" : ""}`}>{d.status}</span></td>
                  <td>{new Date(d.created_at).toLocaleDateString()}</td>
                  <td>
                    <button className="danger small" onClick={() => handleDeleteDoc(d.id)}>Delete</button>
                  </td>
                </tr>
              ))}
              {filteredDocs.length === 0 && (
                <tr><td colSpan={5} className="empty">No documents yet</td></tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
