import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function ServicesPage() {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", duration_minutes: 30, price: "" });

  const load = async () => {
    try {
      setServices(await api.getServices());
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
      if (data.price) data.price = Number(data.price);
      else delete data.price;
      data.duration_minutes = Number(data.duration_minutes);
      await api.createService(data);
      setForm({ name: "", description: "", duration_minutes: 30, price: "" });
      setShowForm(false);
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
          <h1>Services</h1>
          <button onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "+ New Service"}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
      </header>

      {showForm && (
        <section className="card form-card">
          <h2>New Service</h2>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="form-group">
              <label>Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Dental Cleaning"
                required
              />
            </div>
            <div className="form-group">
              <label>Duration (minutes)</label>
              <input
                type="number"
                value={form.duration_minutes}
                onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
                min="5"
                required
              />
            </div>
            <div className="form-group">
              <label>Price</label>
              <input
                type="number"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                placeholder="5000"
              />
            </div>
            <div className="form-group full-width">
              <label>Description</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Brief description of the service"
                rows={3}
              />
            </div>
            <div className="form-actions">
              <button type="submit">Add Service</button>
            </div>
          </form>
        </section>
      )}

      <section className="card">
        <h2>All Services ({services.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Duration</th>
              <th>Price</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {services.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.duration_minutes} min</td>
                <td>{s.price ? `$${s.price}` : "—"}</td>
                <td>{s.description || "—"}</td>
              </tr>
            ))}
            {services.length === 0 && (
              <tr><td colSpan={4} className="empty">No services yet</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
