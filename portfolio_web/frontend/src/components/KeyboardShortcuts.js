import React, { useState, useEffect, useCallback } from 'react';
import { FiX } from 'react-icons/fi';
import './KeyboardShortcuts.css';

const SHORTCUTS = [
  { keys: ['?'], description: 'Toggle this shortcuts panel' },
  { keys: ['G', 'D'], description: 'Go to Dashboard' },
  { keys: ['G', 'O'], description: 'Go to Optimizer' },
  { keys: ['G', 'B'], description: 'Go to Builder' },
  { keys: ['G', 'M'], description: 'Go to Market Data' },
  { keys: ['Esc'], description: 'Close overlay / cancel' },
];

const NAVIGATION_MAP = {
  d: '/',
  o: '/portfolio',
  b: '/portfolio-builder',
  m: '/market-data',
};

const KeyboardShortcuts = () => {
  const [visible, setVisible] = useState(false);
  const [pendingG, setPendingG] = useState(false);

  const handleKeyDown = useCallback((e) => {
    // Don't trigger when typing in inputs/textareas
    const tag = (e.target?.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target?.isContentEditable) {
      return;
    }

    if (e.key === 'Escape') {
      setVisible(false);
      setPendingG(false);
      return;
    }

    if (e.key === '?') {
      e.preventDefault();
      setVisible((prev) => !prev);
      setPendingG(false);
      return;
    }

    if (e.key === 'g' || e.key === 'G') {
      if (!pendingG) {
        setPendingG(true);
        // Reset after 1 second if no follow-up key
        setTimeout(() => setPendingG(false), 1000);
        return;
      }
    }

    if (pendingG) {
      const target = NAVIGATION_MAP[e.key.toLowerCase()];
      if (target && window.location.pathname !== target) {
        window.location.href = target;
      }
      setPendingG(false);
    }
  }, [pendingG]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!visible) return null;

  return (
    <div className="kb-overlay" onClick={() => setVisible(false)}>
      <div className="kb-panel" onClick={(e) => e.stopPropagation()}>
        <div className="kb-header">
          <h3>Keyboard Shortcuts</h3>
          <button className="kb-close" onClick={() => setVisible(false)} aria-label="Close shortcuts">
            <FiX />
          </button>
        </div>
        <div className="kb-list">
          {SHORTCUTS.map((shortcut) => (
            <div className="kb-row" key={shortcut.description}>
              <div className="kb-keys">
                {shortcut.keys.map((key, i) => (
                  <React.Fragment key={key}>
                    {i > 0 && <span className="kb-then">then</span>}
                    <kbd className="kb-key">{key}</kbd>
                  </React.Fragment>
                ))}
              </div>
              <span className="kb-desc">{shortcut.description}</span>
            </div>
          ))}
        </div>
        <p className="kb-hint">Press <kbd>?</kbd> to toggle this panel</p>
      </div>
    </div>
  );
};

export default KeyboardShortcuts;
