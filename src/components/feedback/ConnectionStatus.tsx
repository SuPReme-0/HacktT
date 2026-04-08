import { useEffect } from 'react';
import { useSystemStore } from '../../store/systemStore';

export default function ConnectionStatus() {
  const { backendConnected, initSystem } = useSystemStore();

  // Initialize WebSocket listeners on mount
  useEffect(() => {
    // This will set up the /ws/telemetry listener and update backendConnected state
    const cleanupPromise = initSystem();
    
    // Handle the cleanup function if initSystem returns one
    const cleanup = async () => {
      const result = await cleanupPromise;
      if (typeof result === 'function') {
        result();
      }
    };
    
    return () => {
      cleanup();
    };
  }, [initSystem]);

  return (
    <div className="fixed top-4 right-4 z-40 flex items-center gap-2 px-3 py-1.5 rounded-full 
                    bg-[#0a0a0a]/80 border border-[#1f1f1f] backdrop-blur-sm transition-all duration-300
                    hover:border-[#00f3ff]/50 hover:shadow-[0_0_15px_rgba(0,243,255,0.2)]">
      <div className={`w-2 h-2 rounded-full transition-all duration-300 ${
        backendConnected 
          ? 'bg-green-500 animate-pulse shadow-[0_0_10px_rgba(34,197,94,0.5)]' 
          : 'bg-red-500 animate-pulse shadow-[0_0_10px_rgba(239,68,68,0.5)]'
      }`} />
      <span className={`text-[8px] uppercase tracking-widest transition-colors duration-300 ${
        backendConnected ? 'text-green-400' : 'text-red-400'
      }`}>
        {backendConnected ? 'Core Online' : 'Core Offline'}
      </span>
    </div>
  );
}