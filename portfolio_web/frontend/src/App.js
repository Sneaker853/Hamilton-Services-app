import React, { useEffect, useMemo, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import './App.css';
import logoPlaceholder from './assets/hamilton-services-logo-notext.png';
import {
  FiActivity,
  FiBarChart2,
  FiBriefcase,
  FiGrid,
  FiInfo,
  FiLogIn,
  FiLogOut,
  FiMenu,
  FiSettings,
  FiShield,
  FiX,
} from 'react-icons/fi';

// Theme
import { useThemeStore, applyTheme } from './components/ThemeContext';

// Pages
import Dashboard from './pages/Dashboard';
import PortfolioGenerator from './pages/PortfolioGenerator';
import PortfolioBuilder from './pages/PortfolioBuilder';
import MarketData from './pages/MarketData';
import AdminPanel from './pages/AdminPanel';
import Login from './pages/Login';
import Mission from './pages/Mission';

// API base URL strategy:
// - Production: explicit REACT_APP_API_URL (or same-origin /api reverse proxy)
// - Development: CRA proxy fallback
const IS_PRODUCTION = process.env.NODE_ENV === 'production';
const API_BASE = process.env.REACT_APP_API_URL || (IS_PRODUCTION ? '/api' : '/api');
const ADMIN_ALLOWED_EMAIL = 'loris@spatafora.ca';
axios.defaults.withCredentials = true;

const getCookieValue = (name) => {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

axios.interceptors.request.use((config) => {
  const method = String(config?.method || 'get').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = getCookieValue('portfolio_csrf_token');
    if (csrfToken) {
      config.headers = config.headers || {};
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});

// Handle 401 errors globally
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('authUser');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

function AppContent() {
  const [apiHealth, setApiHealth] = useState('checking');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [authUser, setAuthUser] = useState(null);
  const [guestMode, setGuestMode] = useState(false);
  const location = useLocation();
  const theme = useThemeStore(state => state.theme);

  // Initialize theme on mount
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    // Check API health on load
    const healthUrl = API_BASE.replace(/\/api$/, '') + '/health';
    axios.get(healthUrl, { timeout: 5000 })
      .then(() => setApiHealth('healthy'))
      .catch(err => {
        console.warn('API health check failed:', err.message);
        setApiHealth('error');
      });
  }, []);

  useEffect(() => {
    const loadUser = async () => {
      const guest = localStorage.getItem('guestMode') === 'true';
      setGuestMode(guest);

      if (guest) {
        setAuthUser(null);
        return;
      }

      try {
        const response = await axios.get(`${API_BASE}/auth/me`, { timeout: 5000 });
        const user = response?.data;
        if (user?.email) {
          setAuthUser(user);
          localStorage.setItem('authUser', JSON.stringify(user));
          return;
        }
      } catch (_err) {
      }

      const stored = localStorage.getItem('authUser');
      if (stored) {
        try {
          setAuthUser(JSON.parse(stored));
        } catch (err) {
          setAuthUser(null);
        }
      } else {
        setAuthUser(null);
      }
    };

    loadUser();
    window.addEventListener('storage', loadUser);
    return () => window.removeEventListener('storage', loadUser);
  }, []);

  const handleSignOut = async () => {
    try {
      await axios.post(`${API_BASE}/auth/logout`, {}, { timeout: 5000 });
    } catch (err) {
      console.warn('Logout request failed:', err.message);
    }

    localStorage.removeItem('authUser');
    localStorage.removeItem('guestMode');
    setAuthUser(null);
    setGuestMode(false);
    window.location.href = '/';
  };

  const handleGuestLogin = () => {
    localStorage.removeItem('guestMode');
    localStorage.removeItem('authUser');
    setGuestMode(false);
    setAuthUser(null);
    window.location.href = '/login';
  };

  const menuItems = [
    { path: '/', label: 'Dashboard', icon: FiGrid },
    { path: '/portfolio', label: 'Optimizer', icon: FiActivity },
    { path: '/portfolio-builder', label: 'Builder', icon: FiBriefcase },
    { path: '/market-data', label: 'Market Data', icon: FiBarChart2 },
    { path: '/mission', label: 'Mission', icon: FiInfo },
    { path: '/admin', label: 'Admin', icon: FiShield },
  ];

  const userInitial = useMemo(() => {
    if (!authUser?.email) return 'U';
    return authUser.email.charAt(0).toUpperCase();
  }, [authUser]);

  if (!authUser && !guestMode) {
    return <Login apiBase={API_BASE} fullScreen />;
  }

  const canAccessAdmin = String(authUser?.email || '').trim().toLowerCase() === ADMIN_ALLOWED_EMAIL;

  const NavLinks = ({ onNavigate }) => (
    <nav className="shell-nav-links">
      {menuItems
        .filter((item) => item.path !== '/admin' || canAccessAdmin)
        .map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`shell-nav-link ${isActive ? 'active' : ''}`}
              onClick={onNavigate}
            >
              <Icon className="shell-nav-icon" />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
    </nav>
  );

  return (
    <div className="shell-app">
      <button
        className="shell-mobile-toggle"
        onClick={() => setMobileNavOpen(true)}
        aria-label="Open navigation"
      >
        <FiMenu />
      </button>

      {mobileNavOpen && <div className="shell-mobile-overlay" onClick={() => setMobileNavOpen(false)} />}

      <aside className={`shell-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="shell-sidebar-header">
          <Link to="/" className="shell-brand" onClick={() => setMobileNavOpen(false)}>
            <img src={logoPlaceholder} alt="Logo" className="shell-logo-image" />
            {!sidebarCollapsed && (
              <div className="shell-brand-text">
                <strong>Hamilton Services</strong>
                <small>ANALYTICS</small>
              </div>
            )}
          </Link>
          <div className="shell-header-actions">
            <button
              className="shell-icon-btn desktop"
              onClick={() => setSidebarCollapsed((prev) => !prev)}
              aria-label="Toggle desktop sidebar"
            >
              <FiMenu />
            </button>
            <button
              className="shell-icon-btn mobile"
              onClick={() => setMobileNavOpen(false)}
              aria-label="Close mobile navigation"
            >
              <FiX />
            </button>
          </div>
        </div>

        <NavLinks onNavigate={() => setMobileNavOpen(false)} />

        <div className="shell-status-card">
          <span className={`shell-status-dot ${apiHealth}`} />
          {!sidebarCollapsed && <span>System {apiHealth === 'healthy' ? 'Online' : apiHealth}</span>}
        </div>

        <div className="shell-sidebar-footer">
          <div className="shell-user-row">
            <div className="shell-user-avatar">{userInitial}</div>
            {!sidebarCollapsed && (
              <div className="shell-user-meta">
                <span>{authUser?.email || 'Guest user'}</span>
                <small>{authUser ? 'Signed in' : 'Guest mode'}</small>
              </div>
            )}
          </div>
          {authUser && (
            <button className="shell-logout-btn" onClick={handleSignOut}>
              <FiLogOut />
              {!sidebarCollapsed && <span>Sign out</span>}
            </button>
          )}
          {!authUser && guestMode && (
            <button className="shell-logout-btn" onClick={handleGuestLogin}>
              <FiLogIn />
              {!sidebarCollapsed && <span>Log in</span>}
            </button>
          )}
        </div>
      </aside>

      <aside className={`shell-sidebar-mobile ${mobileNavOpen ? 'open' : ''}`}>
        <div className="shell-sidebar-header">
          <Link to="/" className="shell-brand" onClick={() => setMobileNavOpen(false)}>
            <img src={logoPlaceholder} alt="Logo" className="shell-logo-image" />
            <div className="shell-brand-text">
              <strong>Hamilton Services</strong>
              <small>ANALYTICS</small>
            </div>
          </Link>
          <button
            className="shell-icon-btn mobile"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close mobile navigation"
          >
            <FiX />
          </button>
        </div>
        <NavLinks onNavigate={() => setMobileNavOpen(false)} />
      </aside>

      <main className={`shell-main ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <header className="shell-topbar">
          <div>
            <h1>{menuItems.find((item) => item.path === location.pathname)?.label || 'Hamilton Services'}</h1>
            <p>Institutional-grade analytics for modern portfolio management.</p>
          </div>
          {canAccessAdmin && (
            <button
              className="shell-icon-btn"
              onClick={() => window.location.assign('/admin')}
              aria-label="Open settings"
            >
              <FiSettings />
            </button>
          )}
        </header>
        <Routes>
          <Route path="/" element={<Dashboard apiBase={API_BASE} />} />
          <Route path="/portfolio" element={<PortfolioGenerator apiBase={API_BASE} />} />
          <Route path="/portfolio-builder" element={<PortfolioBuilder apiBase={API_BASE} />} />
          <Route path="/market-data" element={<MarketData apiBase={API_BASE} />} />
          <Route path="/mission" element={<Mission />} />
          <Route path="/admin" element={canAccessAdmin ? <AdminPanel apiBase={API_BASE} /> : <Navigate to="/" replace />} />
          <Route path="/login" element={<Login apiBase={API_BASE} />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
