import { useState, useEffect } from 'react';
import { useSystemStore } from '../store/systemStore';

export default function useBackendHealth() {
  const { setBackendConnected } = useSystemStore();
  const [backendConnected, setConnected] = useState(false);

  const checkBackendHealth = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/health', {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      setConnected(response.ok);
      setBackendConnected(response.ok);
    } catch {
      setConnected(false);
      setBackendConnected(false);
    }
  };

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 5000);
    return () => clearInterval(interval);
  }, [setBackendConnected]);

  return { backendConnected, setBackendConnected };
}