import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import './App.css';
import logoPlaceholder from './assets/hamilton-services-logo-notext.png';
import {
  FiActivity,
  FiBarChart2,
  FiBell,
  FiBriefcase,
  FiColumns,
  FiCrosshair,
  FiGrid,
  FiHelpCircle,
  FiInfo,
  FiLock,
  FiLogIn,
  FiLogOut,
  FiMail,
  FiMenu,
  FiSettings,
  FiShield,
  FiStar,
  FiTrendingUp,
  FiX,
} from 'react-icons/fi';
import { RiScales3Line } from 'react-icons/ri';

// Theme
import { useThemeStore, applyTheme } from './components/ThemeContext';
import { LanguageProvider, useLanguage } from './components';

// Pages
import Dashboard from './pages/Dashboard';
import PortfolioGenerator from './pages/PortfolioGenerator';
import PortfolioBuilder from './pages/PortfolioBuilder';
import MarketData from './pages/MarketData';
import AdminPanel from './pages/AdminPanel';
import Login from './pages/Login';
import Mission from './pages/Mission';
import Contact from './pages/Contact';
import ChangePassword from './pages/ChangePassword';
import PortfolioComparison from './pages/PortfolioComparison';
import StockComparison from './pages/StockComparison';
import HelpDocs from './pages/HelpDocs';
import SharedPortfolio from './pages/SharedPortfolio';
import Watchlist from './pages/Watchlist';
import Alerts from './pages/Alerts';
import PerformanceDashboard from './pages/PerformanceDashboard';
import Goals from './pages/Goals';
import Landing from './pages/Landing';
import KeyboardShortcuts from './components/KeyboardShortcuts';
import OnboardingWizard from './components/OnboardingWizard';

// API base URL strategy:
// - Production: explicit REACT_APP_API_URL (or same-origin /api reverse proxy)
// - Development: CRA proxy fallback
const IS_PRODUCTION = process.env.NODE_ENV === 'production';
const PROD_API_BASE = 'https://hamilton-services-backend.onrender.com/api';
const normalizeApiBase = (value) => String(value || '').trim().replace(/\/+$/, '');
const isLocalApiBase = (value) => /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(String(value || '').trim());
const ENV_API_BASE = normalizeApiBase(process.env.REACT_APP_API_URL);
const API_BASE = (() => {
  if (IS_PRODUCTION) {
    if (ENV_API_BASE && !isLocalApiBase(ENV_API_BASE)) {
      return ENV_API_BASE;
    }
    return PROD_API_BASE;
  }
  return ENV_API_BASE || '/api';
})();
const ADMIN_ALLOWED_EMAIL = 'loris@spatafora.ca';
axios.defaults.withCredentials = false;

const shouldSendCredentials = (requestUrl) => {
  const url = String(requestUrl || '');
  return (
    url.includes('/auth/')
    || url.includes('/portfolios')
    || url.includes('/admin/')
    || url.includes('/watchlist')
    || url.includes('/alerts')
    || url.includes('/goals')
    || url.includes('/portfolio-performance')
    || url.includes('/dashboard-performance')
  );
};

const getCookieValue = (name) => {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
};

axios.interceptors.request.use((config) => {
  const requestUrl = String(config?.url || '');
  if (shouldSendCredentials(requestUrl)) {
    config.withCredentials = true;
  } else if (typeof config.withCredentials === 'undefined') {
    // Public market/portfolio compute endpoints should avoid ambient session cookies.
    config.withCredentials = false;
  }

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
  const [showOnboarding, setShowOnboarding] = useState(false);
  const location = useLocation();
  const theme = useThemeStore(state => state.theme);
  const { lang, setLang, t, tt } = useLanguage();

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
      // Check auth credentials BEFORE guestMode so logging in clears guest state
      const stored = localStorage.getItem('authUser');
      const csrfCookie = getCookieValue('portfolio_csrf_token');

      if (stored || csrfCookie) {
        try {
          const response = await axios.get(`${API_BASE}/auth/me`, { timeout: 5000, withCredentials: true });
          const user = response?.data;
          if (user?.email) {
            setAuthUser(user);
            setGuestMode(false);
            localStorage.setItem('authUser', JSON.stringify(user));
            localStorage.removeItem('guestMode');
            return;
          }
        } catch (_err) {
          // Session validation failed — clear stale cached user
          localStorage.removeItem('authUser');
        }
      }

      // No valid auth — check guest mode
      const guest = localStorage.getItem('guestMode') === 'true';
      setGuestMode(guest);
      setAuthUser(null);
    };

    loadUser();
    window.addEventListener('storage', loadUser);
    return () => window.removeEventListener('storage', loadUser);
  }, []);

  const handleSignOut = async () => {
    try {
      await axios.post(`${API_BASE}/auth/logout`, {}, { timeout: 5000, withCredentials: true });
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
    { path: '/', label: t('nav_dashboard'), icon: FiGrid },
    { path: '/portfolio', label: t('nav_optimizer'), icon: FiActivity },
    { path: '/portfolio-builder', label: t('nav_builder'), icon: FiBriefcase },
    { path: '/market-data', label: t('nav_market'), icon: FiBarChart2 },
    { path: '/compare', label: t('nav_compare'), icon: FiColumns },
    { path: '/compare-stocks', label: t('nav_stocks'), icon: RiScales3Line },
    { path: '/watchlist', label: t('nav_watchlist'), icon: FiStar, requiresAuth: true },
    { path: '/alerts', label: t('nav_alerts'), icon: FiBell, requiresAuth: true },
    { path: '/performance', label: t('nav_performance'), icon: FiTrendingUp, requiresAuth: true },
    { path: '/goals', label: t('nav_goals'), icon: FiCrosshair, requiresAuth: true },
    { path: '/help', label: t('nav_help'), icon: FiHelpCircle },
    { path: '/mission', label: 'Mission', icon: FiInfo },
    { path: '/contact', label: 'Contact', icon: FiMail },
    { path: '/change-password', label: 'Password', icon: FiLock, requiresAuth: true },
    { path: '/admin', label: t('nav_admin'), icon: FiShield },
  ];

  const userInitial = useMemo(() => {
    if (!authUser?.email) return 'U';
    return authUser.email.charAt(0).toUpperCase();
  }, [authUser]);

  if (!authUser && !guestMode) {
    // Allow /login path through so Sign In works
    if (location.pathname === '/login') {
      return <Login apiBase={API_BASE} fullScreen />;
    }
    return (
      <Landing
        onContinueAsGuest={() => {
          localStorage.setItem('guestMode', 'true');
          setGuestMode(true);
          if (!localStorage.getItem('onboardingComplete')) {
            setShowOnboarding(true);
          }
        }}
        onLogin={() => {
          window.location.href = '/login';
        }}
      />
    );
  }

  const canAccessAdmin = String(authUser?.email || '').trim().toLowerCase() === ADMIN_ALLOWED_EMAIL;

  const NavLinks = ({ onNavigate }) => (
    <nav className="shell-nav-links">
      {menuItems
        .filter((item) => item.path !== '/admin' || canAccessAdmin)
        .filter((item) => !item.requiresAuth || authUser)
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
      <a href="#main-content" className="skip-to-main">{tt('Skip to main content')}</a>
      <KeyboardShortcuts />
      {showOnboarding && <OnboardingWizard onClose={() => setShowOnboarding(false)} />}
      <button
        className="shell-mobile-toggle"
        onClick={() => setMobileNavOpen(true)}
        aria-label={tt('Open navigation')}
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
                <small>{tt('ANALYTICS')}</small>
              </div>
            )}
          </Link>
          <div className="shell-header-actions">
            <button
              className="shell-icon-btn desktop"
              onClick={() => setSidebarCollapsed((prev) => !prev)}
              aria-label={tt('Toggle desktop sidebar')}
            >
              <FiMenu />
            </button>
            <button
              className="shell-icon-btn mobile"
              onClick={() => setMobileNavOpen(false)}
              aria-label={tt('Close mobile navigation')}
            >
              <FiX />
            </button>
          </div>
        </div>

        <NavLinks onNavigate={() => setMobileNavOpen(false)} />

        <div className="shell-status-card">
          <span className={`shell-status-dot ${apiHealth}`} />
          {!sidebarCollapsed && <span>{lang === 'fr' ? 'Système' : 'System'} {apiHealth === 'healthy' ? (lang === 'fr' ? 'En ligne' : 'Online') : apiHealth}</span>}
        </div>

        <div className="shell-sidebar-footer">
          <div className="shell-user-row">
            <div className="shell-user-avatar">{userInitial}</div>
            {!sidebarCollapsed && (
              <div className="shell-user-meta">
                <span>{authUser?.email || (lang === 'fr' ? 'Invité' : 'Guest user')}</span>
                <small>{authUser ? (lang === 'fr' ? 'Connecté' : 'Signed in') : (lang === 'fr' ? 'Mode invité' : 'Guest mode')}</small>
              </div>
            )}
          </div>
          <button
            className="shell-logout-btn"
            onClick={() => setLang(lang === 'en' ? 'fr' : 'en')}
            title={lang === 'en' ? 'Passer en français' : 'Switch to English'}
          >
            <FiSettings />
            {!sidebarCollapsed && <span>{lang === 'en' ? 'FR' : 'EN'}</span>}
          </button>
          {authUser && (
            <button className="shell-logout-btn" onClick={handleSignOut}>
              <FiLogOut />
              {!sidebarCollapsed && <span>{t('nav_sign_out', 'Sign out')}</span>}
            </button>
          )}
          {!authUser && guestMode && (
            <button className="shell-logout-btn" onClick={handleGuestLogin}>
              <FiLogIn />
              {!sidebarCollapsed && <span>{t('nav_sign_in', 'Log in')}</span>}
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
              <small>{tt('ANALYTICS')}</small>
            </div>
          </Link>
          <button
            className="shell-icon-btn mobile"
            onClick={() => setMobileNavOpen(false)}
            aria-label={tt('Close mobile navigation')}
          >
            <FiX />
          </button>
        </div>
        <NavLinks onNavigate={() => setMobileNavOpen(false)} />
      </aside>

      <main id="main-content" className={`shell-main ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <header className="shell-topbar">
          <div>
            <h1>{menuItems.find((item) => item.path === location.pathname)?.label || 'Hamilton Services'}</h1>
            <p>{tt('Institutional-grade analytics for modern portfolio management.')}</p>
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
          <Route path="/compare" element={<PortfolioComparison apiBase={API_BASE} />} />
          <Route path="/compare-stocks" element={<StockComparison apiBase={API_BASE} />} />
          <Route path="/watchlist" element={authUser ? <Watchlist apiBase={API_BASE} /> : <Navigate to="/login" replace />} />
          <Route path="/alerts" element={authUser ? <Alerts apiBase={API_BASE} /> : <Navigate to="/login" replace />} />
          <Route path="/performance" element={authUser ? <PerformanceDashboard apiBase={API_BASE} /> : <Navigate to="/login" replace />} />
          <Route path="/goals" element={authUser ? <Goals apiBase={API_BASE} /> : <Navigate to="/login" replace />} />
          <Route path="/help" element={<HelpDocs />} />
          <Route path="/shared/:shareToken" element={<SharedPortfolio apiBase={API_BASE} />} />
          <Route path="/mission" element={<Mission />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/change-password" element={authUser ? <ChangePassword apiBase={API_BASE} /> : <Navigate to="/login" replace />} />
          <Route path="/admin" element={canAccessAdmin ? <AdminPanel apiBase={API_BASE} /> : <Navigate to="/" replace />} />
          <Route path="/login" element={<Login apiBase={API_BASE} />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <LanguageProvider>
      <Router>
        <AppContent />
      </Router>
    </LanguageProvider>
  );
}

export default App;
