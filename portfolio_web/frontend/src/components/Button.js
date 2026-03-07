/**
 * Enhanced Button Component
 * Professional button with hover states, loading states, and variants
 */
import React from 'react';
import './Button.css';

export const Button = ({
  children,
  onClick,
  variant = 'primary', // primary, secondary, tertiary, danger, success
  size = 'medium', // small, medium, large
  loading = false,
  disabled = false,
  icon = null,
  iconPosition = 'left',
  fullWidth = false,
  className = '',
  ...props
}) => {
  const buttonClasses = [
    'btn',
    `btn-${variant}`,
    `btn-${size}`,
    fullWidth && 'btn-full-width',
    loading && 'btn-loading',
    disabled && 'btn-disabled',
    className
  ].filter(Boolean).join(' ');

  return (
    <button
      className={buttonClasses}
      onClick={onClick}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="btn-spinner" />
      ) : (
        <>
          {icon && iconPosition === 'left' && <span className="btn-icon btn-icon-left">{icon}</span>}
          <span className="btn-text">{children}</span>
          {icon && iconPosition === 'right' && <span className="btn-icon btn-icon-right">{icon}</span>}
        </>
      )}
    </button>
  );
};

export default Button;
