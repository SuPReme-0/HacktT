import { useState, useRef, useCallback, useEffect } from 'react';
import { listen, UnlistenFn } from '@tauri-apps/api/event';

export interface BootSequenceReturn {
  isBooting: boolean;
  bootProgress: number;
  initError: string | null;
  handleRetry: () => void;
  isReady: boolean;
}

export default function useBootSequence(
  initSystem: () => Promise<void | (() => void)>, 
  checkSession: () => Promise<void>,
  timeoutMs: number = 30000 // Default 30 second timeout
): BootSequenceReturn {
  const [isBooting, setIsBooting] = useState<boolean>(true);
  const [bootProgress, setBootProgress] = useState<number>(0);
  const [initError, setInitError] = useState<string | null>(null);
  const [isReady, setIsReady] = useState<boolean>(false);
  
  const bootIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cleanupRef = useRef<(() => void) | undefined>(undefined);
  const abortControllerRef = useRef<AbortController | null>(null);
  const telemetryUnlistenRef = useRef<UnlistenFn | undefined>(undefined);
  const isMountedRef = useRef<boolean>(true);

  // ======================================================================
  // 1. COMPONENT MOUNT TRACKING (Prevent state updates on unmounted components)
  // ======================================================================
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // ======================================================================
  // 2. REAL-TIME BOOT PROGRESS SYNC (WebSocket Telemetry)
  // ======================================================================
  const setupTelemetryListener = useCallback(async () => {
    try {
      telemetryUnlistenRef.current = await listen('telemetry', (event: any) => {
        // Only update state if component is still mounted
        if (!isMountedRef.current) return;
        
        if (event.payload?.type === 'boot_progress') {
          // Backend sends real progress updates during model loading
          const progress = event.payload.progress;
          if (typeof progress === 'number' && progress >= 0 && progress <= 100) {
            setBootProgress(progress);
            if (progress >= 100) {
              // Backend confirmed full boot
              completeBoot();
            }
          }
        }
      });
    } catch (error) {
      console.warn('BootSequence: Failed to setup telemetry listener:', error);
      // Fallback to simulated progress if WebSocket isn't available
      startProgressSimulation();
    }
  }, []);

  const startProgressSimulation = useCallback(() => {
    // Clear any existing interval first
    if (bootIntervalRef.current) {
      clearInterval(bootIntervalRef.current);
      bootIntervalRef.current = null;
    }
    
    setBootProgress(0);
    
    bootIntervalRef.current = setInterval(() => {
      // Only update state if component is still mounted
      if (!isMountedRef.current) return;
      
      setBootProgress(prev => {
        if (prev >= 90) return 90; // Hold at 90% until backend confirms
        return prev + 10;
      });
    }, 150);
  }, []);

  const stopProgressSimulation = useCallback(() => {
    if (bootIntervalRef.current) {
      clearInterval(bootIntervalRef.current);
      bootIntervalRef.current = null;
    }
  }, []);

  const completeBoot = useCallback(() => {
    // Only proceed if component is still mounted
    if (!isMountedRef.current) return;
    
    stopProgressSimulation();
    setBootProgress(100);
    setIsReady(true);
    // Smooth transition before unmounting boot screen
    setTimeout(() => {
      if (isMountedRef.current) {
        setIsBooting(false);
      }
    }, 800);
  }, [stopProgressSimulation]);

  // ======================================================================
  // 3. BOOT EXECUTION WITH TIMEOUT, ABORT SUPPORT & CRASH GUARDS
  // ======================================================================
  const executeBoot = useCallback(async () => {
    // Create new AbortController for this boot attempt
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;
    
    // Reset state
    setInitError(null);
    setIsBooting(true);
    setIsReady(false);
    setBootProgress(0);
    
    // Start simulated progress as fallback
    startProgressSimulation();
    
    // Setup real-time telemetry listener
    await setupTelemetryListener();

    try {
      // Race condition: timeout vs actual init
      const initPromise = initSystem();
      const timeoutPromise = new Promise<never>((_, reject) => {
        const timeoutId = setTimeout(() => {
          reject(new Error('Backend initialization timed out'));
        }, timeoutMs);
        // Clean up timeout if init completes first
        signal.addEventListener('abort', () => clearTimeout(timeoutId));
      });
      
      // Wait for either init to complete or timeout
      const cleanup = await Promise.race([initPromise, timeoutPromise]);
      
      // Store cleanup function if returned
      if (typeof cleanup === 'function') {
        cleanupRef.current = cleanup;
      }
      
      // Check auth session
      await checkSession();
      
      // If we get here, boot succeeded
      completeBoot();
      
    } catch (error: any) {
      // Don't update state if component is unmounting or aborted
      if (!isMountedRef.current || signal.aborted) return;
      
      // Stop progress simulation on error
      stopProgressSimulation();
      
      // Distinguish between recoverable and fatal errors
      const isRecoverable = error.message?.includes('timeout') || 
                           error.message?.includes('network') ||
                           error.message?.includes('connection');
      
      setInitError(isRecoverable 
        ? 'Connection to Sovereign Core lost. Retry?' 
        : error.message || 'Failed to establish neural link to OS.');
      
      setIsBooting(false); // Show ErrorBoundary for fatal errors
    }
  }, [initSystem, checkSession, startProgressSimulation, stopProgressSimulation, setupTelemetryListener, completeBoot, timeoutMs]);

  // ======================================================================
  // 4. LIFECYCLE MANAGEMENT WITH CRASH GUARDS
  // ======================================================================
  useEffect(() => {
    executeBoot();
    
    // Cleanup on unmount
    return () => {
      // Mark component as unmounted to prevent state updates
      isMountedRef.current = false;
      
      // Abort any pending async operations
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      
      // Clear progress simulation
      stopProgressSimulation();
      
      // Cleanup telemetry listener
      if (telemetryUnlistenRef.current) {
        telemetryUnlistenRef.current();
        telemetryUnlistenRef.current = undefined;
      }
      
      // Run cleanup function from initSystem if provided
      if (typeof cleanupRef.current === 'function') {
        try {
          cleanupRef.current();
        } catch (error) {
          console.warn('BootSequence: Cleanup function failed:', error);
        }
        cleanupRef.current = undefined;
      }
    };
  }, [executeBoot, stopProgressSimulation]);

  return { 
    isBooting, 
    bootProgress, 
    initError, 
    handleRetry: executeBoot,
    isReady
  };
}