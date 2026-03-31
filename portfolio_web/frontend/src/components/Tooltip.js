import React, { useState, useRef, useEffect } from 'react';
import ReactDOM from 'react-dom';
import './Tooltip.css';

export const Tooltip = ({ text, children, position = 'top' }) => {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const [adjustedPosition, setAdjustedPosition] = useState(position);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (visible && wrapRef.current) {
      const rect = wrapRef.current.getBoundingClientRect();
      const gap = 8;
      let top, left, pos = position;

      // Calculate initial position
      if (pos === 'top') {
        top = rect.top - gap;
        left = rect.left + rect.width / 2;
      } else if (pos === 'bottom') {
        top = rect.bottom + gap;
        left = rect.left + rect.width / 2;
      } else if (pos === 'left') {
        top = rect.top + rect.height / 2;
        left = rect.left - gap;
      } else {
        top = rect.top + rect.height / 2;
        left = rect.right + gap;
      }

      // Flip if needed
      if (pos === 'top' && rect.top < 80) pos = 'bottom';
      if (pos === 'bottom' && rect.bottom > window.innerHeight - 80) pos = 'top';
      if (pos === 'left' && rect.left < 280) pos = 'right';
      if (pos === 'right' && rect.right > window.innerWidth - 280) pos = 'left';

      // Recalculate after flip
      if (pos === 'top') { top = rect.top - gap; left = rect.left + rect.width / 2; }
      else if (pos === 'bottom') { top = rect.bottom + gap; left = rect.left + rect.width / 2; }
      else if (pos === 'left') { top = rect.top + rect.height / 2; left = rect.left - gap; }
      else { top = rect.top + rect.height / 2; left = rect.right + gap; }

      setAdjustedPosition(pos);
      setCoords({ top, left });
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
      {visible && ReactDOM.createPortal(
        <span
          className={`tooltip-bubble tooltip-${adjustedPosition}`}
          role="tooltip"
          style={{ top: coords.top, left: coords.left }}
        >
          {text}
        </span>,
        document.body
      )}
    </span>
  );
};

export const HelpIcon = ({ text, position }) => (
  <Tooltip text={text} position={position}>
    <span className="tooltip-help-icon" tabIndex={0} aria-label="Help">?</span>
  </Tooltip>
);
