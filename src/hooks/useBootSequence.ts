import { useState, useRef, useCallback, useEffect } from 'react';

export default function useBootSequence(
  initSystem: () => Promise<void | (() => void)>, 
  checkSession: () => Promise<void>
) {
  const [isBooting, setIsBooting] = useState<boolean>(true);
  const [bootProgress, setBootProgress] = useState<number>(0);
  const [initError, setInitError] = useState<string | null>(null);
  
  const bootIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const cleanupRef = useRef<(() => void) | void>(undefined); // Store the cleanup function

  const startProgressSimulation = useCallback(() => {
    setBootProgress(0);
    if (bootIntervalRef.current) clearInterval(bootIntervalRef.current);
    
    bootIntervalRef.current = setInterval(() => {
      setBootProgress(prev => {
        if (prev >= 90) return 90; // Hold at 90% until backend confirms
        return prev + 10;
      });
    }, 150);
  }, []);

  const executeBoot = useCallback(async () => {
    setInitError(null);
    setIsBooting(true);
    startProgressSimulation();

    try {
      // 1. Init Hardware & Sockets (Store cleanup if returned)
      cleanupRef.current = await initSystem();
      
      // 2. Check Auth Session
      await checkSession();
      
      // 3. Success -> Push to 100% and finish
      setBootProgress(100);
      if (bootIntervalRef.current) clearInterval(bootIntervalRef.current);
      
      setTimeout(() => setIsBooting(false), 800);
      
    } catch (error: any) {
      if (bootIntervalRef.current) clearInterval(bootIntervalRef.current);
      setInitError(error.message || 'Failed to establish neural link to OS.');
      setIsBooting(false); // We stop booting to show the ErrorBoundary
    }
  }, [initSystem, checkSession, startProgressSimulation]);

  // Initial boot on mount
  useEffect(() => {
    executeBoot();
    
    // Cleanup on unmount
    return () => {
      if (bootIntervalRef.current) clearInterval(bootIntervalRef.current);
      if (typeof cleanupRef.current === 'function') cleanupRef.current();
    };
  }, [executeBoot]);

  return { 
    isBooting, 
    bootProgress, 
    initError, 
    handleRetry: executeBoot // handleRetry just re-runs the execute sequence
  };
}