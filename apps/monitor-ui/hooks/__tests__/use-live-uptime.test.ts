import { renderHook, act } from '@testing-library/react';
import { useLiveUptime } from '../use-live-uptime';

describe('useLiveUptime', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should calculate uptime from start time', () => {
    const startTime = new Date('2024-01-01T00:00:00Z').toISOString();
    jest.setSystemTime(new Date('2024-01-01T01:30:45Z'));

    const { result } = renderHook(() => useLiveUptime(startTime, undefined));

    expect(result.current).toBe('1h 30m 45s');
  });

  it('should handle undefined start time and use initial uptime', () => {
    const { result } = renderHook(() => useLiveUptime(undefined, 3665));

    expect(result.current).toBe('1h 1m 5s');
  });

  it('should handle both undefined', () => {
    const { result } = renderHook(() => useLiveUptime(undefined, undefined));

    expect(result.current).toBe('0h 0m 0s');
  });

  it('should update every second', () => {
    const startTime = new Date('2024-01-01T00:00:00Z').toISOString();
    jest.setSystemTime(new Date('2024-01-01T00:00:10Z'));

    const { result } = renderHook(() => useLiveUptime(startTime, undefined));

    expect(result.current).toBe('0h 0m 10s');

    act(() => {
      jest.setSystemTime(new Date('2024-01-01T00:00:11Z'));
      jest.advanceTimersByTime(1000);
    });

    expect(result.current).toBe('0h 0m 11s');
  });

  it('should format hours correctly', () => {
    const startTime = new Date('2024-01-01T00:00:00Z').toISOString();
    jest.setSystemTime(new Date('2024-01-01T05:00:00Z'));

    const { result } = renderHook(() => useLiveUptime(startTime, undefined));

    expect(result.current).toBe('5h 0m 0s');
  });

  it('should format minutes correctly', () => {
    const startTime = new Date('2024-01-01T00:00:00Z').toISOString();
    jest.setSystemTime(new Date('2024-01-01T00:45:30Z'));

    const { result } = renderHook(() => useLiveUptime(startTime, undefined));

    expect(result.current).toBe('0h 45m 30s');
  });

  it('should format seconds only', () => {
    const startTime = new Date('2024-01-01T00:00:00Z').toISOString();
    jest.setSystemTime(new Date('2024-01-01T00:00:30Z'));

    const { result } = renderHook(() => useLiveUptime(startTime, undefined));

    expect(result.current).toBe('0h 0m 30s');
  });

  it('should handle invalid date string', () => {
    const { result } = renderHook(() => useLiveUptime('invalid-date', undefined));

    // Invalid dates result in NaN, which will show as NaNh NaNm NaNs
    expect(result.current).toMatch(/NaN/);
  });

  it('should handle negative time (future dates)', () => {
    const startTime = new Date('2024-01-02T00:00:00Z').toISOString();
    jest.setSystemTime(new Date('2024-01-01T00:00:00Z'));

    const { result } = renderHook(() => useLiveUptime(startTime, undefined));

    // Future dates result in negative seconds
    expect(result.current).toMatch(/-/);
  });

  it('should use initial uptime when no start time', () => {
    const { result } = renderHook(() => useLiveUptime(undefined, 7200));

    expect(result.current).toBe('2h 0m 0s');

    act(() => {
      jest.advanceTimersByTime(1000);
    });

    // Should increment from initial uptime
    expect(result.current).toBe('2h 0m 1s');
  });
});
