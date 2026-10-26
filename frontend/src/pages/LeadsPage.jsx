import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const LEAD_STATUSES = ["new", "contacted", "converted", "lost"];

export default function LeadsPage() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const load = async () => {
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      setLeads(await api.getLeads(params));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [statusFilter]);

  const handleStatusChange = async (lead, newStatus) => {
    try {
      await api.updateLead(lead.id, { status: newStatus });
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
          <h1>Leads</h1>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="filter-select">
            <option value="">All Statuses</option>
            {LEAD_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        {error && <div className="error">{error}</div>}
      </header>

      <section className="card">
        <h2>All Leads ({leads.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Service</th>
              <th>Preferred Date</th>
              <th>Status</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {leads.map((l) => (
              <tr key={l.id}>
                <td>{l.name || "—"}</td>
                <td>{l.phone || "—"}</td>
                <td>{l.service || "—"}</td>
                <td>{l.preferred_date || "—"}</td>
                <td>
                  <select
                    value={l.status}
                    onChange={(e) => handleStatusChange(l, e.target.value)}
                    className={`badge badge-${l.status}`}
                  >
                    {LEAD_STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </td>
                <td>{l.source || "—"}</td>
              </tr>
            ))}
            {leads.length === 0 && (
              <tr><td colSpan={6} className="empty">No leads found</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
