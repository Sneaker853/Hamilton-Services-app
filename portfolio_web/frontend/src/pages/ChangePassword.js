import React, { useState } from 'react';
import axios from 'axios';
import { FiLock } from 'react-icons/fi';
import './ChangePassword.css';

const ChangePassword = ({ apiBase }) => {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!currentPassword || !newPassword || !confirmPassword) {
      setError('All fields are required.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    if (newPassword === currentPassword) {
      setError('New password must be different from current password.');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(
        `${apiBase}/auth/change-password`,
        { current_password: currentPassword, new_password: newPassword },
        { withCredentials: true, timeout: 15000 }
      );
      setSuccess(response?.data?.message || 'Password changed successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.message || 'Failed to change password.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="change-pw-root">
      <section className="change-pw-glass change-pw-hero">
        <div className="change-pw-hero-icon"><FiLock /></div>
        <h1>Change Password</h1>
        <p>Update your account password. You'll need to enter your current password for verification.</p>
      </section>

      <section className="change-pw-glass change-pw-card">
        <form onSubmit={handleSubmit} className="change-pw-form">
          <div className="change-pw-form-group">
            <label>Current Password</label>
            <input
              type="password"
              className="form-control"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          <div className="change-pw-form-group">
            <label>New Password</label>
            <input
              type="password"
              className="form-control"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="••••••••"
            />
            <span className="change-pw-hint">
              Min 10 characters, include uppercase, lowercase, number, and symbol.
            </span>
          </div>
          <div className="change-pw-form-group">
            <label>Confirm New Password</label>
            <input
              type="password"
              className="form-control"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && <div className="change-pw-error">{error}</div>}
          {success && <div className="change-pw-success">{success}</div>}

          <button type="submit" className="change-pw-submit" disabled={loading}>
            {loading ? 'Updating...' : 'Update Password'}
          </button>
        </form>
      </section>
    </div>
  );
};

export default ChangePassword;
