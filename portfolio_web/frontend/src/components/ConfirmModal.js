import React from 'react';
import './ConfirmModal.css';

export const ConfirmModal = ({ open, title, message, confirmLabel = 'Confirm', cancelLabel = 'Cancel', onConfirm, onCancel, variant = 'primary' }) => {
  if (!open) return null;

  return (
    <div className="confirm-modal-overlay" onClick={onCancel} role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
      <div className="confirm-modal-glass" onClick={(e) => e.stopPropagation()}>
        <h3 id="confirm-modal-title" className="confirm-modal-title">{title}</h3>
        <p className="confirm-modal-message">{message}</p>
        <div className="confirm-modal-actions">
          <button type="button" className="confirm-modal-btn cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className={`confirm-modal-btn ${variant}`} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
