import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function WhatsAppPage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const [testTo, setTestTo] = useState("");
  const [testText, setTestText] = useState("Hello from Clinic AI — test message");
  const [sending, setSending] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const load = async () => {
    try {
      setError("");
      setStatus(await api.getWhatsAppStatus());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await load();
  };

  const handleSendTest = async (e) => {
    e.preventDefault();
    setSending(true);
    setTestResult(null);
    setError("");
    try {
      const result = await api.sendWhatsAppTest(testTo.trim(), testText);
      setTestResult({ ok: result?.ok ?? true, detail: result?.detail || "Message sent" });
    } catch (err) {
      setTestResult({ ok: false, detail: err.message });
    } finally {
      setSending(false);
    }
  };

  if (loading) return <div className="container">Loading...</div>;

  const configured = !!status?.configured;
  const graphApi = status?.graph_api || null;
  const graphOk = configured && graphApi ? graphApi.ok === true : null;

  let overall = "Not configured";
  let overallTone = "bad";
  if (configured && graphOk === true) {
    overall = "Connected";
    overallTone = "ok";
  } else if (configured && graphOk === false) {
    overall = "Graph API error";
    overallTone = "warn";
  } else if (configured) {
    overall = "Configured — check pending";
    overallTone = "warn";
  }

  const creds = [
    {
      label: "Phone Number ID",
      value: status?.phone_number_id || "not set",
      present: !!status?.phone_number_id && status.phone_number_id !== "not set",
    },
    { label: "WABA ID", value: status?.waba_id || "not set", present: !!status?.waba_id },
    { label: "Access Token", value: status?.access_token, present: status?.access_token === "set" },
    {
      label: "Webhook Verify Token",
      value: status?.webhook_verify_token,
      present: status?.webhook_verify_token === "set",
    },
    {
      label: "App Secret (HMAC)",
      value: status?.app_secret,
      present: status?.app_secret === "set",
    },
    { label: "API Version", value: status?.api_version || "—", present: !!status?.api_version },
  ];

  return (
    <div className="container">
      <header>
        <div className="header-row">
          <h1>WhatsApp Connection</h1>
          <div className="header-actions">
            <button onClick={handleRefresh} disabled={refreshing}>
              {refreshing ? "Checking..." : "↻ Check again"}
            </button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
      </header>

      <div className="card">
        <div className="wa-summary">
          <div>
            <h2>Connection status</h2>
            <p className="wa-sub">
              Reports which Meta Cloud API credentials are configured and validates the access token against the
              Graph API live.
            </p>
          </div>
          <span className={`wa-pill wa-pill-${overallTone}`}>{overall}</span>
        </div>

        <div className="wa-creds">
          {creds.map((c) => (
            <div key={c.label} className="wa-cred">
              <span className="wa-cred-label">{c.label}</span>
              <span className={`wa-cred-value ${c.present ? "" : "wa-missing"}`}>{c.value}</span>
            </div>
          ))}
        </div>

        {graphApi && (
          <div className={`wa-graph ${graphApi.ok ? "wa-graph-ok" : "wa-graph-fail"}`}>
            {graphApi.ok
              ? "✓ Valid credentials — Meta accepted the access token."
              : `✗ Graph API rejected the check (HTTP ${graphApi.status_code || "?"}${graphApi.code ? `, code ${graphApi.code}` : ""}): ${graphApi.error}`}
          </div>
        )}
        {!configured && (
          <div className="wa-graph wa-graph-fail">
            Fill <code>WHATSAPP_PHONE_NUMBER_ID</code> and <code>WHATSAPP_ACCESS_TOKEN</code> in{" "}
            <code>backend/.env</code>, then restart the API.
          </div>
        )}
      </div>
      <div className="card">
        <h2>Send a test message</h2>
        <p className="wa-sub">
          Sends a real outbound WhatsApp message. Works for phone numbers Meta allows in your app&apos;s current
          mode (whitelisted recipients in development, users who replied &quot;join&quot; in production).
        </p>
        <form onSubmit={handleSendTest}>
          <div className="form-group">
            <label>Recipient phone (E.164)</label>
            <input
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              placeholder="+15550101111"
              required
            />
          </div>
          <div className="form-group">
            <label>Message</label>
            <textarea value={testText} onChange={(e) => setTestText(e.target.value)} rows={2} maxLength={4096} required />
          </div>
          <div className="form-actions">
            <button type="submit" disabled={sending}>
              {sending ? "Sending..." : "Send test message"}
            </button>
          </div>
        </form>
        {testResult && (
          <div className={`wa-test-result ${testResult.ok ? "wa-test-ok" : "wa-test-fail"}`}>
            <strong>{testResult.ok ? "Sent" : "Failed"}:</strong> {testResult.detail}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Before you go live</h2>
        <ol className="wa-checklist">
          <li>
            Create a Meta business app at developers.facebook.com and add the <strong>WhatsApp</strong> product.
            Copy the <strong>Phone number ID</strong> and permanent <strong>access token</strong> from
            WhatsApp → API Setup into <code>backend/.env</code>.
          </li>
          <li>
            Set <code>WHATSAPP_APP_SECRET</code> (Meta app dashboard → Settings → Basic). When set, every webhook
            request must carry a valid <code>X-Hub-Signature-256</code>, and invalid ones are rejected with 403.
          </li>
          <li>
            Generate a verify token with <code>python scripts/generate_webhook_token.py</code>, then register
            this backend&apos;s public URL as the webhook callback (<code>GET /whatsapp/webhook</code>) in the
            Meta app dashboard.
          </li>
          <li>
            Link your Phone Number ID to a clinic so inbound messages route to the right tenant:{" "}
            <code>python scripts/link_clinic_whatsapp.py &lt;phone_number_id&gt; &lt;clinic_slug&gt;</code>.
          </li>
          <li>
            Ensure the clinic has doctors, services and availability, otherwise the bot can&apos;t offer slots:{" "}
            <code>python scripts/seed_demo_availability.py</code>.
          </li>
        </ol>
        <p className="wa-sub">
          Full step-by-step guide with ngrok tunnel setup: see{" "}
          <code>backend/README.md → Connect WhatsApp (Meta Cloud API)</code>.
        </p>
      </div>
    </div>
  );
}