import { renderHook, act } from '@testing-library/react';
import { useRelativeTime } from '../use-relative-time';

// Mock date
const mockNow = new Date('2024-01-01T12:00:00Z');

describe('useRelativeTime', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(mockNow);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should return "0s ago" for current time', () => {
    const { result } = renderHook(() => useRelativeTime(mockNow.toISOString()));
    expect(result.current).toBe('0s ago');
  });

  it('should return seconds ago', () => {
    const past = new Date(mockNow.getTime() - 30 * 1000);
    const { result } = renderHook(() => useRelativeTime(past.toISOString()));
    expect(result.current).toBe('30s ago');
  });

  it('should return minutes ago', () => {
    const past = new Date(mockNow.getTime() - 5 * 60 * 1000);
    const { result } = renderHook(() => useRelativeTime(past.toISOString()));
    expect(result.current).toBe('5m ago');
  });

  it('should return hours ago', () => {
    const past = new Date(mockNow.getTime() - 3 * 60 * 60 * 1000);
    const { result } = renderHook(() => useRelativeTime(past.toISOString()));
    expect(result.current).toBe('3h ago');
  });

  it('should return hours for days', () => {
    const past = new Date(mockNow.getTime() - 2 * 24 * 60 * 60 * 1000);
    const { result } = renderHook(() => useRelativeTime(past.toISOString()));
    expect(result.current).toBe('48h ago');
  });

  it('should update every second', () => {
    const past = new Date(mockNow.getTime() - 1000);
    const { result } = renderHook(() => useRelativeTime(past.toISOString()));

    expect(result.current).toBe('1s ago');

    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(result.current).toBe('2s ago');
  });

  it('should handle invalid date', () => {
    const { result } = renderHook(() => useRelativeTime('invalid-date'));
    expect(result.current).toBe('NaNh ago');
  });

  it('should handle null date', () => {
    const { result } = renderHook(() => useRelativeTime(null as any));
    expect(result.current).toBe('N/A');
  });

  it('should handle undefined date', () => {
    const { result } = renderHook(() => useRelativeTime(undefined as any));
    expect(result.current).toBe('N/A');
  });

  it('should cleanup interval on unmount', () => {
    const { unmount } = renderHook(() => useRelativeTime(mockNow.toISOString()));
    const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
