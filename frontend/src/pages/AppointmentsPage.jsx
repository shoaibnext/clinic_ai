import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const STATUSES = ["scheduled", "cancelled", "completed"];

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState([]);
  const [patients, setPatients] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ patient_id: "", doctor_id: "", service_id: "", service_label: "", scheduled_at: "" });
  const [editingId, setEditingId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");

  const load = async () => {
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      const [a, p, d, s] = await Promise.all([
        api.getAppointments(params),
        api.getPatients(),
        api.getDoctors(),
        api.getServices(),
      ]);
      setAppointments(a);
      setPatients(p);
      setDoctors(d);
      setServices(s);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [statusFilter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const data = {
        patient_id: Number(form.patient_id),
        doctor_id: form.doctor_id ? Number(form.doctor_id) : null,
        service_id: form.service_id ? Number(form.service_id) : null,
        service_label: form.service_label || null,
        scheduled_at: form.scheduled_at || null,
      };
      if (editingId) {
        await api.updateAppointment(editingId, data);
      } else {
        await api.createAppointment(data);
      }
      setForm({ patient_id: "", doctor_id: "", service_id: "", service_label: "", scheduled_at: "" });
      setEditingId(null);
      setShowForm(false);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleEdit = (appt) => {
    setForm({
      patient_id: appt.patient_id,
      doctor_id: appt.doctor_id || "",
      service_id: appt.service_id || "",
      service_label: appt.service_label || "",
      scheduled_at: appt.scheduled_at ? appt.scheduled_at.slice(0, 16) : "",
    });
    setEditingId(appt.id);
    setShowForm(true);
  };

  const handleStatusChange = async (appt, newStatus) => {
    try {
      await api.updateAppointment(appt.id, { status: newStatus });
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this appointment?")) return;
    try {
      await api.deleteAppointment(id);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const patientName = (id) => {
    const p = patients.find((x) => x.id === id);
    return p ? (p.full_name || p.phone_number) : `#${id}`;
  };

  const doctorName = (id) => {
    const d = doctors.find((x) => x.id === id);
    return d ? d.name : `#${id}`;
  };

  const serviceName = (id) => {
    const s = services.find((x) => x.id === id);
    return s ? s.name : `#${id}`;
  };

  if (loading) return <div className="container">Loading...</div>;

  return (
    <div className="container">
      <header>
        <div className="header-row">
          <h1>Appointments</h1>
          <button onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ patient_id: "", doctor_id: "", service_id: "", service_label: "", scheduled_at: "" }); }}>
            {showForm ? "Cancel" : "+ New Appointment"}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
      </header>

      {showForm && (
        <section className="card form-card">
          <h2>{editingId ? "Edit Appointment" : "New Appointment"}</h2>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="form-group">
              <label>Patient</label>
              <select value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })} required>
                <option value="">Select patient</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>{p.full_name || p.phone_number}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Doctor</label>
              <select value={form.doctor_id} onChange={(e) => setForm({ ...form, doctor_id: e.target.value })}>
                <option value="">Any available</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Service</label>
              <select value={form.service_id} onChange={(e) => setForm({ ...form, service_id: e.target.value })}>
                <option value="">Select service</option>
                {services.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Service Label (or select above)</label>
              <input
                placeholder="e.g. Dental cleaning"
                value={form.service_label}
                onChange={(e) => setForm({ ...form, service_label: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Date & Time</label>
              <input
                type="datetime-local"
                value={form.scheduled_at}
                onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
              />
            </div>
            <div className="form-actions">
              <button type="submit">{editingId ? "Update" : "Book"}</button>
            </div>
          </form>
        </section>
      )}

      <section className="card">
        <div className="header-row">
          <h2>All Appointments ({appointments.length})</h2>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="filter-select">
            <option value="">All Statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <table>
          <thead>
            <tr>
              <th>Patient</th>
              <th>Doctor</th>
              <th>Service</th>
              <th>Scheduled</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {appointments.map((a) => (
              <tr key={a.id}>
                <td>{patientName(a.patient_id)}</td>
                <td>{a.doctor_id ? doctorName(a.doctor_id) : "—"}</td>
                <td>{a.service_label || (a.service_id ? serviceName(a.service_id) : "—")}</td>
                <td>{a.scheduled_at ? new Date(a.scheduled_at).toLocaleString() : "—"}</td>
                <td>
                  <select
                    value={a.status}
                    onChange={(e) => handleStatusChange(a, e.target.value)}
                    className={`badge badge-${a.status}`}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <button onClick={() => handleEdit(a)} className="small">Edit</button>
                  <button className="danger small" onClick={() => handleDelete(a.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {appointments.length === 0 && (
              <tr><td colSpan={6} className="empty">No appointments found</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
