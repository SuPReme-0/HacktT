import { useEffect, useRef, useCallback, useState } from 'react';
import { useSystemStore } from '../store/systemStore';

export interface BackendHealthReturn {
  backendConnected: boolean;
  isChecking: boolean;
  lastCheckTime: Date | null;
  checkNow: () => Promise<void>;
}

export default function useBackendHealth(
  checkIntervalMs: number = 5000 // Default 5 second interval
): BackendHealthReturn {
  const { backendConnected, setBackendConnected, checkBackendHealth } = useSystemStore();
  const [isChecking, setIsChecking] = useState<boolean>(false);
  const [lastCheckTime, setLastCheckTime] = useState<Date | null>(null);
  
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // ======================================================================
  // 1. HEALTH CHECK WITH ABORT SUPPORT
  // ======================================================================
  const performHealthCheck = useCallback(async () => {
    if (isChecking) return; // Prevent concurrent checks
    
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;
    
    setIsChecking(true);
    
    try {
      await checkBackendHealth();
      setLastCheckTime(new Date());
    } catch (error) {
      if (!signal.aborted) {
        console.warn('BackendHealth: Health check failed:', error);
        setBackendConnected(false);
      }
    } finally {
      if (!signal.aborted) {
        setIsChecking(false);
      }
    }
  }, [isChecking, checkBackendHealth, setBackendConnected]);

  // ======================================================================
  // 2. INTERVAL MANAGEMENT
  // ======================================================================
  useEffect(() => {
    // Perform immediate check on mount
    performHealthCheck();
    
    // Setup interval for periodic checks
    intervalRef.current = setInterval(() => {
      performHealthCheck();
    }, checkIntervalMs);
    
    // Cleanup on unmount
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [performHealthCheck, checkIntervalMs]);

  // ======================================================================
  // 3. PUBLIC API
  // ======================================================================
  const checkNow = useCallback(async () => {
    // Clear existing interval to prevent duplicate checks
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    
    await performHealthCheck();
    
    // Restart interval
    intervalRef.current = setInterval(() => {
      performHealthCheck();
    }, checkIntervalMs);
  }, [performHealthCheck, checkIntervalMs]);

  return {
    backendConnected,
    isChecking,
    lastCheckTime,
    checkNow
  };
}