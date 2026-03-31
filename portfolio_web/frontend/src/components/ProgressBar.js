import React, { useState, useEffect, useRef } from 'react';
import './ProgressBar.css';

/**
 * ProgressBar with time-based animation and ETA display.
 * 
 * Props:
 *   active     - Whether the operation is in progress
 *   estimatedMs - Expected total duration in milliseconds
 *   label      - Text label shown above the bar (e.g. "Generating portfolio...")
 *   onComplete - Optional callback when progress reaches 100%
 */
const ProgressBar = ({ active, estimatedMs = 5000, label = 'Processing...', onComplete }) => {
  const [progress, setProgress] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef(null);
  const frameRef = useRef(null);

  useEffect(() => {
    if (!active) {
      // When operation finishes, jump to 100% briefly, then reset
      if (progress > 0 && progress < 100) {
        setProgress(100);
        if (onComplete) onComplete();
        const timeout = setTimeout(() => {
          setProgress(0);
          setElapsed(0);
        }, 600);
        return () => clearTimeout(timeout);
      }
      setProgress(0);
      setElapsed(0);
      startTimeRef.current = null;
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      return;
    }

    startTimeRef.current = Date.now();

    const tick = () => {
      if (!startTimeRef.current) return;
      const elapsedMs = Date.now() - startTimeRef.current;
      setElapsed(elapsedMs);

      // Asymptotic curve: approaches 95% as time progresses, never reaches 100% until done
      const ratio = elapsedMs / estimatedMs;
      const pct = Math.min(95, 100 * (1 - Math.exp(-2.5 * ratio)));
      setProgress(pct);

      frameRef.current = requestAnimationFrame(tick);
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [active, estimatedMs, onComplete, progress]);

  if (!active && progress === 0) return null;

  const remainingMs = Math.max(0, estimatedMs - elapsed);
  const remainingSec = Math.ceil(remainingMs / 1000);
  const elapsedSec = Math.floor(elapsed / 1000);

  const formatTime = (seconds) => {
    if (seconds >= 60) {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return `${m}m ${s}s`;
    }
    return `${seconds}s`;
  };

  return (
    <div className="progress-bar-container" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}>
      <div className="progress-bar-header">
        <span className="progress-bar-label">{label}</span>
        <span className="progress-bar-eta">
          {progress < 100
            ? `~${formatTime(remainingSec)} remaining`
            : 'Complete!'
          }
        </span>
      </div>
      <div className="progress-bar-track">
        <div
          className={`progress-bar-fill ${progress >= 100 ? 'complete' : ''}`}
          style={{ width: `${Math.round(progress)}%` }}
        />
      </div>
      <div className="progress-bar-footer">
        <span className="progress-bar-pct">{Math.round(progress)}%</span>
        <span className="progress-bar-elapsed">{formatTime(elapsedSec)} elapsed</span>
      </div>
    </div>
  );
};

export default ProgressBar;
