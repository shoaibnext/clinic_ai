const API_BASE = import.meta.env.VITE_API_BASE || "/api";

function getToken() {
  return localStorage.getItem("token");
}

function setToken(token) {
  localStorage.setItem("token", token);
}

function clearToken() {
  localStorage.removeItem("token");
}

function isLoggedIn() {
  return !!getToken();
}

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API error ${response.status}: ${body}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }).then((data) => {
      setToken(data.access_token);
      localStorage.setItem("clinic_id", data.clinic_id);
      localStorage.setItem("user_id", data.user_id);
      localStorage.setItem("role", data.role);
      return data;
    }),

  logout: () => {
    clearToken();
    localStorage.removeItem("clinic_id");
    localStorage.removeItem("user_id");
    localStorage.removeItem("role");
  },

  isLoggedIn,

  // Doctors
  getDoctors: () => request("/doctors"),
  createDoctor: (data) => request("/doctors", { method: "POST", body: JSON.stringify(data) }),
  getDoctor: (id) => request(`/doctors/${id}`),
  getDoctorServices: (id) => request(`/doctors/${id}/services`),

  // Services
  getServices: () => request("/services"),
  createService: (data) => request("/services", { method: "POST", body: JSON.stringify(data) }),
  getService: (id) => request(`/services/${id}`),

  // Patients
  getPatients: () => request("/patients"),
  createPatient: (data) => request("/patients", { method: "POST", body: JSON.stringify(data) }),
  getPatient: (id) => request(`/patients/${id}`),
  updatePatient: (id, data) => request(`/patients/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deletePatient: (id) => request(`/patients/${id}`, { method: "DELETE" }),

  // Appointments
  getAppointments: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/appointments${qs ? `?${qs}` : ""}`);
  },
  createAppointment: (data) => request("/appointments", { method: "POST", body: JSON.stringify(data) }),
  getAppointment: (id) => request(`/appointments/${id}`),
  updateAppointment: (id, data) => request(`/appointments/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAppointment: (id) => request(`/appointments/${id}`, { method: "DELETE" }),

  // Leads
  getLeads: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/leads${qs ? `?${qs}` : ""}`);
  },
  getLead: (id) => request(`/leads/${id}`),
  updateLead: (id, data) => request(`/leads/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  // Conversations
  getConversations: () => request("/conversations"),
  getConversation: (id) => request(`/conversations/${id}`),
  updateConversation: (id, data) => request(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  // Availability
  getAvailability: () => request("/availability"),
  createAvailability: (data) => request("/availability", { method: "POST", body: JSON.stringify(data) }),
  getSlots: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/availability/slots${qs ? `?${qs}` : ""}`);
  },

  // Knowledge
  getKnowledgeBases: () => request("/knowledge/bases"),
  createKnowledgeBase: (data) => request("/knowledge/bases", { method: "POST", body: JSON.stringify(data) }),
  getDocuments: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/knowledge/documents${qs ? `?${qs}` : ""}`);
  },
  createDocument: (data) => request("/knowledge/documents", { method: "POST", body: JSON.stringify(data) }),
  deleteDocument: (id) => request(`/knowledge/documents/${id}`, { method: "DELETE" }),
  searchKnowledge: (query) => request("/knowledge/search", { method: "POST", body: JSON.stringify({ query }) }),

  // WhatsApp
  testAiChat: (message) => request("/ai/chat", { method: "POST", body: JSON.stringify({ message }) }),
  getWhatsAppStatus: () => request("/whatsapp/status"),
  sendWhatsAppTest: (toPhone, text) =>
    request("/whatsapp/test", { method: "POST", body: JSON.stringify({ to_phone: toPhone, text }) }),
};
