import React from "react";
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate } from "react-router-dom";
import { api } from "./api.js";

import LoginPage from "./pages/LoginPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import AppointmentsPage from "./pages/AppointmentsPage.jsx";
import PatientsPage from "./pages/PatientsPage.jsx";
import DoctorsPage from "./pages/DoctorsPage.jsx";
import ServicesPage from "./pages/ServicesPage.jsx";
import ConversationsPage from "./pages/ConversationsPage.jsx";
import LeadsPage from "./pages/LeadsPage.jsx";
import KnowledgePage from "./pages/KnowledgePage.jsx";
import WhatsAppPage from "./pages/WhatsAppPage.jsx";

function PrivateRoute({ children }) {
  return api.isLoggedIn() ? children : <Navigate to="/login" />;
}

function Sidebar() {
  const location = useLocation();
  const links = [
    { to: "/", label: "Dashboard", icon: "\u2302" },
    { to: "/appointments", label: "Appointments", icon: "\u2611" },
    { to: "/patients", label: "Patients", icon: "\u263A" },
    { to: "/doctors", label: "Doctors", icon: "\u2695" },
    { to: "/services", label: "Services", icon: "\u2699" },
    { to: "/conversations", label: "Conversations", icon: "\u2709" },
    { to: "/leads", label: "Leads", icon: "\u2605" },
    { to: "/knowledge", label: "Knowledge Base", icon: "\u2606" },
    { to: "/whatsapp", label: "WhatsApp", icon: "\u260E" },
  ];

  const handleLogout = () => {
    api.logout();
    window.location.href = "/login";
  };

  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <h2>Clinic AI</h2>
      </div>
      <ul>
        {links.map((link) => (
          <li key={link.to}>
            <Link to={link.to} className={location.pathname === link.to ? "active" : ""}>
              <span className="nav-icon">{link.icon}</span>
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
      <div className="sidebar-footer">
        <button onClick={handleLogout} className="logout-btn">Sign Out</button>
      </div>
    </nav>
  );
}

function Layout({ children }) {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout><DashboardPage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/appointments"
          element={
            <PrivateRoute>
              <Layout><AppointmentsPage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/patients"
          element={
            <PrivateRoute>
              <Layout><PatientsPage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/doctors"
          element={
            <PrivateRoute>
              <Layout><DoctorsPage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/services"
          element={
            <PrivateRoute>
              <Layout><ServicesPage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/conversations"
          element={
            <PrivateRoute>
              <Layout><ConversationsPage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/leads"
          element={
            <PrivateRoute>
              <Layout><LeadsPage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/knowledge"
          element={
            <PrivateRoute>
              <Layout><KnowledgePage /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/whatsapp"
          element={
            <PrivateRoute>
              <Layout><WhatsAppPage /></Layout>
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
