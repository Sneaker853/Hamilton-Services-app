import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import logo from '../assets/hamilton-services-logo-notext.png';
import './Login.css';

const Login = ({ apiBase, fullScreen = false }) => {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [infoMessage, setInfoMessage] = useState(null);
  const [infoLink, setInfoLink] = useState(null);
  const [resetToken, setResetToken] = useState('');
  const emailInputRef = useRef(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const verifyToken = params.get('verify_token');
    const resetTokenFromQuery = params.get('reset_token');

    const run = async () => {
      if (verifyToken) {
        try {
          const baseUrl = apiBase || '/api';
          await axios.post(`${baseUrl}/auth/verify-email/confirm`, { token: verifyToken }, { withCredentials: true, timeout: 10000 });
          setInfoMessage('Email verified successfully. You can now sign in.');
        } catch (err) {
          setError(err?.response?.data?.message || err?.response?.data?.error || err?.response?.data?.detail || 'Email verification failed.');
        }
      }

      if (resetTokenFromQuery) {
        setResetToken(resetTokenFromQuery);
        setMode('reset');
        setInfoMessage('Enter your new password to complete reset.');
      }
    };

    run();
  }, [apiBase]);

  useEffect(() => {
    if (emailInputRef.current) {
      emailInputRef.current.focus();
    }
  }, [mode]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setInfoMessage(null);
    setInfoLink(null);

    if (mode === 'forgot') {
      if (!email) {
        setError('Email is required.');
        return;
      }
    } else if (mode === 'reset') {
      if (!password) {
        setError('New password is required.');
        return;
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
      if (!resetToken) {
        setError('Reset token is missing. Please use the link from your email.');
        return;
      }
    } else if (!email || !password) {
      setError('Email and password are required.');
      return;
    }

    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const baseUrl = apiBase || '/api';
      if (mode === 'forgot') {
        const response = await axios.post(`${baseUrl}/auth/password-reset/request`, { email }, { timeout: 10000, withCredentials: true });
        const debugLink = response?.data?.debug_link;
        setInfoMessage(response?.data?.message || 'If your account exists, a password reset link has been sent.');
        if (debugLink) {
          setInfoLink(debugLink);
        }
      } else if (mode === 'reset') {
        await axios.post(
          `${baseUrl}/auth/password-reset/confirm`,
          { token: resetToken, new_password: password },
          { timeout: 10000, withCredentials: true }
        );
        setInfoMessage('Password reset successful. You can now sign in.');
        setMode('login');
        setPassword('');
        setConfirmPassword('');
      } else {
        const endpoint = mode === 'signup' ? `${baseUrl}/auth/register` : `${baseUrl}/auth/login`;
        const response = await axios.post(endpoint, { email, password }, { timeout: 10000, withCredentials: true });
        const { user } = response.data || {};
        if (!user) {
          throw new Error('Invalid response from server.');
        }

        localStorage.setItem('authUser', JSON.stringify(user));
        if (mode === 'signup') {
          setInfoMessage('Account created. Please verify your email if required by your environment.');
        }
        window.location.href = '/';
      }
    } catch (err) {
      console.error('Auth error:', err);
      
      let errorMessage = 'Authentication failed.';
      const apiMessage = err?.response?.data?.message || err?.response?.data?.error || err?.response?.data?.detail;
      
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Request timeout. Is the backend running on port 8000?';
      } else if (err.message === 'Network Error') {
        errorMessage = 'Network error. Make sure the backend is running (run start_backend.bat)';
      } else if (err.response?.status === 400) {
        errorMessage = apiMessage || 'Invalid email or password.';
      } else if (err.response?.status === 401) {
        errorMessage = 'Invalid email or password.';
      } else if (err.response?.status === 403) {
        errorMessage = apiMessage || 'Access denied.';
      } else if (apiMessage) {
        errorMessage = apiMessage;
      } else if (err.response?.status === 502 || err.response?.status === 503) {
        errorMessage = 'Backend service unavailable. Make sure the backend is running.';
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={fullScreen ? 'auth-shell' : 'page-container'}>
      <div className={fullScreen ? 'auth-screen' : ''}>
        {fullScreen && (
          <div className="auth-visual">
            <div className="auth-visual-inner">
              <img src={logo} alt="Hamilton Services" className="auth-logo" />
              <h2 className="auth-brand-title">Hamilton Services</h2>
              <p className="auth-tagline">
                Build, optimize, and track portfolios with a pro-grade investing stack.
              </p>
            </div>
          </div>
        )}

        <div className="auth-card">
          {!fullScreen && (
            <div className="page-header">
              <h1>Account</h1>
              <p className="page-subtitle">Sign in or create an account to save portfolios.</p>
            </div>
          )}

          <div className="auth-tabs">
            <button
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => setMode('login')}
              type="button"
            >
              Login
            </button>
            <button
              className={`auth-tab ${mode === 'signup' ? 'active' : ''}`}
              onClick={() => setMode('signup')}
              type="button"
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label>Email</label>
              <input
                ref={emailInputRef}
                type="email"
                className="form-control"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>

            {mode !== 'forgot' && (
              <div className="form-group">
                <label>{mode === 'reset' ? 'New Password' : 'Password'}</label>
                <input
                  type="password"
                  className="form-control"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
                {mode === 'login' && (
                  <div style={{ marginTop: '8px', textAlign: 'right' }}>
                    <button
                      type="button"
                      className="auth-link"
                      onClick={() => {
                        setMode('forgot');
                        setError(null);
                        setInfoMessage(null);
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--primary-teal)',
                        cursor: 'pointer',
                        fontSize: '13px',
                        padding: 0,
                      }}
                    >
                      Forgot password?
                    </button>
                  </div>
                )}
              </div>
            )}

            {(mode === 'signup' || mode === 'reset') && (
              <div className="form-group">
                <label>Confirm Password</label>
                <input
                  type="password"
                  className="form-control"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>
            )}

            {infoMessage && (
              <div className="success-message">
                {infoMessage}
                {infoLink && (
                  <div style={{ marginTop: '8px' }}>
                    <a href={infoLink} style={{ color: 'var(--primary-teal)' }}>
                      Open reset link
                    </a>
                  </div>
                )}
              </div>
            )}
            {error && <div className="error-message">{error}</div>}

            <button className="btn-primary" type="submit" disabled={loading}>
              {loading ? 'Please wait...' : mode === 'signup' ? 'Create Account' : mode === 'forgot' ? 'Send Reset Link' : mode === 'reset' ? 'Set New Password' : 'Sign In'}
            </button>
            {fullScreen && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  localStorage.setItem('guestMode', 'true');
                  window.location.href = '/';
                }}
              >
                Continue without logging in
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
};

export default Login;
