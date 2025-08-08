import { useState, useEffect } from 'react';

/**
 * Hook that provides a relative time string that updates every second
 * @param timestamp - ISO timestamp string
 * @returns Relative time string (e.g., "5s ago", "2m ago")
 */
export function useRelativeTime(timestamp: string | undefined): string {
  const [relativeTime, setRelativeTime] = useState('');

  useEffect(() => {
    if (!timestamp) {
      setRelativeTime('N/A');
      return;
    }

    const updateRelativeTime = () => {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffSecs = Math.floor(diffMs / 1000);

      // Handle negative time (when timestamp is in the future)
      if (diffSecs < 0) {
        setRelativeTime('just now');
        return;
      }

      if (diffSecs < 60) {
        setRelativeTime(`${diffSecs}s ago`);
      } else {
        const diffMins = Math.floor(diffSecs / 60);
        if (diffMins < 60) {
          setRelativeTime(`${diffMins}m ago`);
        } else {
          const diffHours = Math.floor(diffMins / 60);
          setRelativeTime(`${diffHours}h ago`);
        }
      }
    };

    // Update immediately
    updateRelativeTime();

    // Update every second
    const interval = setInterval(updateRelativeTime, 1000);

    return () => clearInterval(interval);
  }, [timestamp]);

  return relativeTime;
}

/**
 * Hook that provides current time that updates every second
 * @returns Current time string
 */
export function useCurrentTime(): string {
  const [currentTime, setCurrentTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      setCurrentTime(new Date().toLocaleString());
    };

    // Update immediately
    updateTime();

    // Update every second
    const interval = setInterval(updateTime, 1000);

    return () => clearInterval(interval);
  }, []);

  return currentTime;
}
