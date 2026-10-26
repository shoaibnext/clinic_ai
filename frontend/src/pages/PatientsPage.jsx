import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function PatientsPage() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ full_name: "", phone_number: "", email: "" });
  const [editingId, setEditingId] = useState(null);

  const load = async () => {
    try {
      setPatients(await api.getPatients());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const data = { ...form };
      if (!data.email) delete data.email;
      if (editingId) {
        await api.updatePatient(editingId, data);
      } else {
        await api.createPatient(data);
      }
      setForm({ full_name: "", phone_number: "", email: "" });
      setEditingId(null);
      setShowForm(false);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleEdit = (p) => {
    setForm({ full_name: p.full_name || "", phone_number: p.phone_number, email: p.email || "" });
    setEditingId(p.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this patient?")) return;
    try {
      await api.deletePatient(id);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return <div className="container">Loading...</div>;

  return (
    <div className="container">
      <header>
        <div className="header-row">
          <h1>Patients</h1>
          <button onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ full_name: "", phone_number: "", email: "" }); }}>
            {showForm ? "Cancel" : "+ New Patient"}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
      </header>

      {showForm && (
        <section className="card form-card">
          <h2>{editingId ? "Edit Patient" : "New Patient"}</h2>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="form-group">
              <label>Full Name</label>
              <input
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Ali Khan"
                required
              />
            </div>
            <div className="form-group">
              <label>Phone Number</label>
              <input
                value={form.phone_number}
                onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                placeholder="+923001234567"
                required
              />
            </div>
            <div className="form-group">
              <label>Email (optional)</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="ali@example.com"
              />
            </div>
            <div className="form-actions">
              <button type="submit">{editingId ? "Update" : "Add"}</button>
            </div>
          </form>
        </section>
      )}

      <section className="card">
        <h2>All Patients ({patients.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Email</th>
              <th>Joined</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.id}>
                <td>{p.full_name || "—"}</td>
                <td>{p.phone_number}</td>
                <td>{p.email || "—"}</td>
                <td>{p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}</td>
                <td>
                  <button onClick={() => handleEdit(p)} className="small">Edit</button>
                  <button className="danger small" onClick={() => handleDelete(p.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={5} className="empty">No patients yet</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
