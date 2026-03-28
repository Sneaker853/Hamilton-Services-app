import React, { useState } from 'react';
import { FiMail, FiMapPin, FiSend } from 'react-icons/fi';
import './Contact.css';

const Contact = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const CONTACT_EMAIL = 'contact@hamilton-services.ca';

  const handleSubmit = (e) => {
    e.preventDefault();
    const mailtoBody = `Name: ${name}\nEmail: ${email}\n\n${message}`;
    const mailtoLink = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject || 'Contact Form Inquiry')}&body=${encodeURIComponent(mailtoBody)}`;
    window.location.href = mailtoLink;
    setSubmitted(true);
  };

  return (
    <div className="contact-root">
      <section className="contact-glass contact-hero">
        <div className="contact-hero-icon"><FiMail /></div>
        <h1>Contact Us</h1>
        <p>Have a question, feedback, or need support? We'd love to hear from you.</p>
      </section>

      <div className="contact-layout">
        <section className="contact-glass contact-info-card">
          <h3>Get in Touch</h3>
          <div className="contact-info-item">
            <FiMail className="contact-info-icon" />
            <div>
              <p className="contact-info-label">Email</p>
              <a href={`mailto:${CONTACT_EMAIL}`} className="contact-info-value">{CONTACT_EMAIL}</a>
            </div>
          </div>
          <div className="contact-info-item">
            <FiMapPin className="contact-info-icon" />
            <div>
              <p className="contact-info-label">Location</p>
              <span className="contact-info-value">Montreal, Canada</span>
            </div>
          </div>
          <div className="contact-response-note">
            <p>We typically respond within 1–2 business days.</p>
          </div>
        </section>

        <section className="contact-glass contact-form-card">
          <h3>Send a Message</h3>
          {submitted ? (
            <div className="contact-success">
              <FiSend className="contact-success-icon" />
              <p>Your email client should have opened with the message pre-filled. If it didn't, please email us directly at <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>
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
              <button type="submit" className="contact-submit-btn">
                <FiSend /> Send Message
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  );
};

export default Contact;
