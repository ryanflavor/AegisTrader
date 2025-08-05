import { useState, useEffect } from 'react';

/**
 * Hook that provides a live uptime that updates every second
 * @param startTime - ISO timestamp string of when the service started
 * @param initialUptimeSeconds - Initial uptime in seconds from the API
 * @returns Formatted uptime string
 */
export function useLiveUptime(startTime: string | undefined, initialUptimeSeconds: number | undefined): string {
  const [uptime, setUptime] = useState('0h 0m 0s');

  useEffect(() => {
    if (!startTime && initialUptimeSeconds === undefined) {
      return;
    }

    const updateUptime = () => {
      let seconds: number;

      if (startTime) {
        // Calculate from start time
        const start = new Date(startTime);
        const now = new Date();
        seconds = Math.floor((now.getTime() - start.getTime()) / 1000);
      } else if (initialUptimeSeconds !== undefined) {
        // Use initial uptime and add elapsed time
        const elapsed = Math.floor((Date.now() - startTimestamp) / 1000);
        seconds = initialUptimeSeconds + elapsed;
      } else {
        seconds = 0;
      }

      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);

      setUptime(`${hours}h ${minutes}m ${secs}s`);
    };

    // Store the timestamp when we first receive the data
    const startTimestamp = Date.now();

    // Update immediately
    updateUptime();

    // Update every second
    const interval = setInterval(updateUptime, 1000);

    return () => clearInterval(interval);
  }, [startTime, initialUptimeSeconds]);

  return uptime;
}
