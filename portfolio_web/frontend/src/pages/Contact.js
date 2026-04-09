import React, { useState } from 'react';
import axios from 'axios';
import { FiMail, FiMapPin, FiSend } from 'react-icons/fi';
import { useLanguage } from '../components';
import './Contact.css';

const IS_PRODUCTION = process.env.NODE_ENV === 'production';
const PROD_API_BASE = 'https://hamilton-services-backend.onrender.com/api';
const normalizeApiBase = (value) => String(value || '').trim().replace(/\/+$/, '');
const isLocalApiBase = (value) => /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(String(value || '').trim());
const API_BASE = (() => {
  const env = normalizeApiBase(process.env.REACT_APP_API_URL);
  if (IS_PRODUCTION) return env && !isLocalApiBase(env) ? env : PROD_API_BASE;
  return env || '/api';
})();

const Contact = () => {
  const { tt } = useLanguage();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const CONTACT_EMAIL = 'contact@hamilton-services.ca';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await axios.post(`${API_BASE}/contact`, {
        name, email, subject, message,
      }, { timeout: 15000 });
      setSubmitted(true);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.message || tt('Unable to send your message. Please try again or email us directly.');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="contact-root">
      <section className="contact-glass contact-hero">
        <div className="contact-hero-icon"><FiMail /></div>
        <h1>{tt('Contact Us')}</h1>
        <p>{tt("Have a question, feedback, or need support? We'd love to hear from you.")}</p>
      </section>

      <div className="contact-layout">
        <section className="contact-glass contact-info-card">
          <h3>{tt('Get in Touch')}</h3>
          <div className="contact-info-item">
            <FiMail className="contact-info-icon" />
            <div>
              <p className="contact-info-label">{tt('Email')}</p>
              <a href={`mailto:${CONTACT_EMAIL}`} className="contact-info-value">{CONTACT_EMAIL}</a>
            </div>
          </div>
          <div className="contact-info-item">
            <FiMapPin className="contact-info-icon" />
            <div>
              <p className="contact-info-label">{tt('Location')}</p>
              <span className="contact-info-value">Montreal, Canada</span>
            </div>
          </div>
          <div className="contact-response-note">
            <p>{tt('We typically respond within 1-2 business days.')}</p>
          </div>
        </section>

        <section className="contact-glass contact-form-card">
          <h3>{tt('Send a Message')}</h3>
          {submitted ? (
            <div className="contact-success">
              <FiSend className="contact-success-icon" />
              <p>{tt('Thank you! Your message has been sent. We typically respond within 1-2 business days.')}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="contact-form">
              <div className="contact-form-row">
                <div className="contact-form-group">
                  <label>Name</label>
                  <input
                    type="text"
                    className="form-control"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    required
                  />
                </div>
                <div className="contact-form-group">
                  <label>Email</label>
                  <input
                    type="email"
                    className="form-control"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                  />
                </div>
              </div>
              <div className="contact-form-group">
                <label>Subject</label>
                <input
                  type="text"
                  className="form-control"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="How can we help?"
                />
              </div>
              <div className="contact-form-group">
                <label>Message</label>
                <textarea
                  className="form-control contact-textarea"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Tell us more about your inquiry..."
                  rows={5}
                  required
                />
              </div>
              {error && <div className="contact-error" role="alert">{error}</div>}
              <button type="submit" className="contact-submit-btn" disabled={submitting}>
                <FiSend /> {submitting ? 'Sending...' : 'Send Message'}
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  );
};

export default Contact;
