/**
 * Assumptions:
 * - This hook runs in a browser environment with window event listeners available.
 * - timeoutMs is greater than warningMs and both values are expressed in milliseconds.
 * - The caller's onTimeout callback performs the actual logout and server cleanup.
 *
 * Backend MUST also enforce idle timeout. This is UX only.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_TIMEOUT_MS = 15 * 60 * 1000;
const DEFAULT_WARNING_MS = 60 * 1000;
const ACTIVITY_THROTTLE_MS = 500;

/**
 * Automatically warn about and expire an inactive client session.
 *
 * This complements the backend's server-side idle timeout. It improves the user
 * experience by warning before logout, but it is not an authorization control.
 *
 * @param {{timeoutMs?: number, warningMs?: number, onTimeout: () => void}} options - Timeout options.
 * @returns {{secondsRemaining: number|null, showWarning: boolean, extendSession: () => void}}
 *   Warning state and a function that resets the inactivity timer.
 */
export function useSessionTimeout({
  timeoutMs = DEFAULT_TIMEOUT_MS,
  warningMs = DEFAULT_WARNING_MS,
  onTimeout,
}) {
  const [secondsRemaining, setSecondsRemaining] = useState(null);
  const [showWarning, setShowWarning] = useState(false);
  const onTimeoutRef = useRef(onTimeout);
  const resetTimerRef = useRef(null);
  const timedOutRef = useRef(false);

  onTimeoutRef.current = onTimeout;

  const extendSession = useCallback(() => {
    timedOutRef.current = false;
    resetTimerRef.current?.();
  }, []);

  useEffect(() => {
    const safeTimeoutMs = Number.isFinite(timeoutMs) && timeoutMs > 0
      ? timeoutMs
      : DEFAULT_TIMEOUT_MS;
    const safeWarningMs = Number.isFinite(warningMs) && warningMs >= 0
      ? Math.min(warningMs, safeTimeoutMs)
      : DEFAULT_WARNING_MS;

    let timeoutId;
    let warningId;
    let warningIntervalId;
    let deadline = 0;
    let lastActivityAt = 0;

    const clearScheduledTimers = () => {
      window.clearTimeout(timeoutId);
      window.clearTimeout(warningId);
      window.clearInterval(warningIntervalId);
    };

    const finishSession = () => {
      clearScheduledTimers();
      timedOutRef.current = true;
      setShowWarning(false);
      setSecondsRemaining(null);
      onTimeoutRef.current?.();
    };

    const startWarning = () => {
      setShowWarning(true);
      setSecondsRemaining(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
      warningIntervalId = window.setInterval(() => {
        const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        setSecondsRemaining(remaining);
      }, 1000);
    };

    const resetTimer = () => {
      clearScheduledTimers();
      deadline = Date.now() + safeTimeoutMs;
      setShowWarning(false);
      setSecondsRemaining(null);

      warningId = window.setTimeout(startWarning, safeTimeoutMs - safeWarningMs);
      timeoutId = window.setTimeout(finishSession, safeTimeoutMs);
    };

    resetTimerRef.current = resetTimer;

    const handleActivity = () => {
      if (timedOutRef.current) {
        return;
      }

      const now = Date.now();
      if (now - lastActivityAt < ACTIVITY_THROTTLE_MS) {
        return;
      }

      lastActivityAt = now;
      resetTimer();
    };

    const activityEvents = ["mousemove", "keydown", "click", "scroll"];
    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, handleActivity, { passive: true });
    });
    resetTimer();

    return () => {
      clearScheduledTimers();
      resetTimerRef.current = null;
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, handleActivity);
      });
    };
  }, [timeoutMs, warningMs]);

  return { secondsRemaining, showWarning, extendSession };
}

/**
 * Usage example:
 *
 * const { secondsRemaining, showWarning, extendSession } = useSessionTimeout({
 *   onTimeout: logout,
 * });
 *
 * return showWarning ? (
 *   <SessionWarning
 *     secondsRemaining={secondsRemaining}
 *     onExtend={extendSession}
 *   />
 * ) : null;
 */
