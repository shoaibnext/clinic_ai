import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function DoctorsPage() {
  const [doctors, setDoctors] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", title: "", specialty: "", bio: "", service_ids: [] });

  const load = async () => {
    try {
      const [d, s] = await Promise.all([api.getDoctors(), api.getServices()]);
      setDoctors(d);
      setServices(s);
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
      await api.createDoctor(form);
      setForm({ name: "", title: "", specialty: "", bio: "", service_ids: [] });
      setShowForm(false);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const toggleService = (serviceId) => {
    setForm((prev) => ({
      ...prev,
      service_ids: prev.service_ids.includes(serviceId)
        ? prev.service_ids.filter((id) => id !== serviceId)
        : [...prev.service_ids, serviceId],
    }));
  };

  if (loading) return <div className="container">Loading...</div>;

  return (
    <div className="container">
      <header>
        <div className="header-row">
          <h1>Doctors</h1>
          <button onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "+ New Doctor"}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
      </header>

      {showForm && (
        <section className="card form-card">
          <h2>New Doctor</h2>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="form-group">
              <label>Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Dr. Ahmed Khan"
                required
              />
            </div>
            <div className="form-group">
              <label>Title</label>
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Senior Dentist"
              />
            </div>
            <div className="form-group">
              <label>Specialty</label>
              <input
                value={form.specialty}
                onChange={(e) => setForm({ ...form, specialty: e.target.value })}
                placeholder="Dentistry"
              />
            </div>
            <div className="form-group full-width">
              <label>Bio</label>
              <textarea
                value={form.bio}
                onChange={(e) => setForm({ ...form, bio: e.target.value })}
                placeholder="Brief bio of the doctor"
                rows={3}
              />
            </div>
            <div className="form-group full-width">
              <label>Services</label>
              <div className="checkbox-group">
                {services.map((s) => (
                  <label key={s.id} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={form.service_ids.includes(s.id)}
                      onChange={() => toggleService(s.id)}
                    />
                    {s.name}
                  </label>
                ))}
                {services.length === 0 && <span className="empty">No services created yet</span>}
              </div>
            </div>
            <div className="form-actions">
              <button type="submit">Add Doctor</button>
            </div>
          </form>
        </section>
      )}

      <section className="card">
        <h2>All Doctors ({doctors.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Title</th>
              <th>Specialty</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {doctors.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td>{d.title || "—"}</td>
                <td>{d.specialty || "—"}</td>
                <td><span className={`badge badge-${d.is_active ? "confirmed" : "cancelled"}`}>{d.is_active ? "Yes" : "No"}</span></td>
              </tr>
            ))}
            {doctors.length === 0 && (
              <tr><td colSpan={4} className="empty">No doctors yet</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
