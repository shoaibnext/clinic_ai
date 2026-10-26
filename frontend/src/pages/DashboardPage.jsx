import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function DashboardPage() {
  const [stats, setStats] = useState({ appointments: 0, patients: 0, conversations: 0, leads: 0 });
  const [upcoming, setUpcoming] = useState([]);
  const [recentConversations, setRecentConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [appointments, patients, conversations, leads] = await Promise.all([
          api.getAppointments({ upcoming: "true" }),
          api.getPatients(),
          api.getConversations(),
          api.getLeads(),
        ]);
        setStats({
          appointments: appointments.length,
          patients: patients.length,
          conversations: conversations.length,
          leads: leads.length,
        });
        setUpcoming(appointments.slice(0, 5));
        setRecentConversations(conversations.slice(0, 5));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return <div className="container">Loading...</div>;

  return (
    <div className="container">
      <header>
        <h1>Dashboard</h1>
        {error && <div className="error">{error}</div>}
      </header>

      <div className="stats-grid">
        <Link to="/appointments" className="stat-card">
          <span className="stat-number">{stats.appointments}</span>
          <span className="stat-label">Upcoming Appointments</span>
        </Link>
        <Link to="/patients" className="stat-card">
          <span className="stat-number">{stats.patients}</span>
          <span className="stat-label">Total Patients</span>
        </Link>
        <Link to="/conversations" className="stat-card">
          <span className="stat-number">{stats.conversations}</span>
          <span className="stat-label">Conversations</span>
        </Link>
        <Link to="/leads" className="stat-card">
          <span className="stat-number">{stats.leads}</span>
          <span className="stat-label">New Leads</span>
        </Link>
      </div>

      <div className="dashboard-grid">
        <section className="card">
          <h2>Upcoming Appointments</h2>
          {upcoming.length === 0 ? (
            <p className="empty">No upcoming appointments</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Service</th>
                  <th>Scheduled</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {upcoming.map((a) => (
                  <tr key={a.id}>
                    <td>Patient #{a.patient_id}</td>
                    <td>{a.service_label || "—"}</td>
                    <td>{a.scheduled_at ? new Date(a.scheduled_at).toLocaleString() : "—"}</td>
                    <td><span className={`badge badge-${a.status}`}>{a.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card">
          <h2>Recent Conversations</h2>
          {recentConversations.length === 0 ? (
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
                {recentConversations.map((c) => (
                  <tr key={c.id}>
                    <td>Patient #{c.patient_id}</td>
                    <td><span className={`badge badge-${c.status}`}>{c.status}</span></td>
                    <td>{c.channel}</td>
                    <td>{new Date(c.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
