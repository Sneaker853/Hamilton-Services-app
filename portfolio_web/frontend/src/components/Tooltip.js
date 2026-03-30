import React, { useState, useRef, useEffect } from 'react';
import './Tooltip.css';

export const Tooltip = ({ text, children, position = 'top' }) => {
  const [visible, setVisible] = useState(false);
  const [adjustedPosition, setAdjustedPosition] = useState(position);
  const tipRef = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (visible && tipRef.current && wrapRef.current) {
      const tipRect = tipRef.current.getBoundingClientRect();
      const wrapRect = wrapRef.current.getBoundingClientRect();

      if (position === 'top' && tipRect.top < 8) {
        setAdjustedPosition('bottom');
      } else if (position === 'bottom' && tipRect.bottom > window.innerHeight - 8) {
        setAdjustedPosition('top');
      } else if (position === 'right' && tipRect.right > window.innerWidth - 8) {
        setAdjustedPosition('left');
      } else if (position === 'left' && tipRect.left < 8) {
        setAdjustedPosition('right');
      } else {
        setAdjustedPosition(position);
      }
    }
  }, [visible, position]);

  return (
    <span
      className="tooltip-wrap"
      ref={wrapRef}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <span className={`tooltip-bubble tooltip-${adjustedPosition}`} ref={tipRef} role="tooltip">
          {text}
        </span>
      )}
    </span>
  );
};

export const HelpIcon = ({ text, position }) => (
  <Tooltip text={text} position={position}>
    <span className="tooltip-help-icon" tabIndex={0} aria-label="Help">?</span>
  </Tooltip>
);
