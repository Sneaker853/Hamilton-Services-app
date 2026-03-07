/**
 * Enhanced Card Component
 * Professional card with hover effects and variants
 */
import React from 'react';
import './Card.css';

export const Card = ({
  children,
  variant = 'default', // default, gradient, glass
  hoverable = true,
  className = '',
  onClick,
  ...props
}) => {
  const cardClasses = [
    'card',
    `card-${variant}`,
    hoverable && 'card-hoverable',
    onClick && 'card-clickable',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={cardClasses} onClick={onClick} {...props}>
      {children}
    </div>
  );
};

export const CardHeader = ({ children, className = '', ...props }) => {
  return (
    <div className={`card-header ${className}`} {...props}>
      {children}
    </div>
  );
};

export const CardBody = ({ children, className = '', ...props }) => {
  return (
    <div className={`card-body ${className}`} {...props}>
      {children}
    </div>
  );
};

export const CardFooter = ({ children, className = '', ...props }) => {
  return (
    <div className={`card-footer ${className}`} {...props}>
      {children}
    </div>
  );
};

export const StatCard = ({ 
  title, 
  value, 
  subtitle, 
  icon, 
  trend,
  trendDirection = 'up', // up, down, neutral
  className = '',
  ...props 
}) => {
  return (
    <Card className={`stat-card ${className}`} {...props}>
      <div className="stat-card-header">
        {icon && <div className="stat-card-icon">{icon}</div>}
        <div className="stat-card-title">{title}</div>
      </div>
      <div className="stat-card-value">{value}</div>
      {(subtitle || trend) && (
        <div className="stat-card-footer">
          {trend && (
            <span className={`stat-card-trend stat-card-trend-${trendDirection}`}>
              {trend}
            </span>
          )}
          {subtitle && <span className="stat-card-subtitle">{subtitle}</span>}
        </div>
      )}
    </Card>
  );
};

export default Card;
