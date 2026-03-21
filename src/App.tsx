import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useSystemStore } from './store/systemStore';
import Dashboard from './components/Dashboard';
import AuthScreen from './components/AuthScreen';
import PassiveBubble from './components/PassiveBubble';
import Starfield from './components/layout/Starfield';

// ======================================================================
// LOADING SCREEN COMPONENT
// ======================================================================
interface BootScreenProps {
  progress: number;
}

const BootScreen: React.FC<BootScreenProps> = ({ progress }) => (
  <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#030305]">
    <div className="text-center space-y-6">
      {/* Logo */}
      <h1 className="text-4xl font-bold tracking-[0.3em] text-white drop-shadow-[0_0_20px_rgba(0,243,255,0.5)]">
        HACKT<span className="text-[#00f3ff]">.AI</span>
      </h1>
      
      {/* Loading Bar */}
      <div className="w-64 h-1 bg-[#1f1f1f] rounded-full overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      
      {/* Status Text */}
      <p className="text-[10px] text-gray-500 uppercase tracking-widest animate-pulse">
        {progress < 30 ? 'Initializing Core...' :
         progress < 60 ? 'Loading Neural Engine...' :
         progress < 90 ? 'Establishing Secure Connection...' :
         'System Ready'}
      </p>
    </div>
  </div>
);

// ======================================================================
// ERROR BOUNDARY COMPONENT
// ======================================================================
interface ErrorBoundaryProps {
  error: string | null;
  onRetry: () => void;
}

const ErrorBoundary: React.FC<ErrorBoundaryProps> = ({ error, onRetry }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#030305]/95 backdrop-blur-md">
    <div className="panel-3d p-8 rounded-2xl max-w-md text-center space-y-4 border border-[#ff003c]/30">
      <div className="text-[#ff003c] text-6xl mb-4">⚠</div>
      <h2 className="text-xl font-bold text-white tracking-widest">SYSTEM ERROR</h2>
      <p className="text-sm text-gray-400 font-mono break-all">{error}</p>
      <button
        onClick={onRetry}
        className="px-6 py-3 bg-[#00f3ff]/10 border border-[#00f3ff]/30 text-[#00f3ff] 
                   hover:bg-[#00f3ff]/20 transition-all text-xs uppercase tracking-widest rounded-lg"
      >
        Retry Initialization
      </button>
    </div>
  </div>
);

// ======================================================================
// BACKEND CONNECTION STATUS COMPONENT
// ======================================================================
interface ConnectionStatusProps {
  connected: boolean;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ connected }) => (
  <div className="fixed top-4 right-4 z-40 flex items-center gap-2 px-3 py-1.5 rounded-full 
                  bg-[#0a0a0a]/80 border border-[#1f1f1f] backdrop-blur-sm">
    <div className={`w-2 h-2 rounded-full ${
      connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
    }`} />
    <span className="text-[8px] text-gray-400 uppercase tracking-widest">
      {connected ? 'Core Online' : 'Core Offline'}
    </span>
  </div>
);

// ======================================================================
// MAIN APP COMPONENT
// ======================================================================
export default function App() {
  const { user, initSystem, checkSession, backendConnected, setBackendConnected, threatLevel } = useSystemStore();
  
  // UI States
  const [currentRoute, setCurrentRoute] = useState<string>(window.location.hash);
  const [bootProgress, setBootProgress] = useState<number>(0);
  const [isBooting, setIsBooting] = useState<boolean>(true);
  const [initError, setInitError] = useState<string | null>(null);
  
  // Refs for cleanup
  const bootIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const healthIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Backend Health Check
  const checkBackendHealth = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/health', {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      setBackendConnected(response.ok);
    } catch {
      setBackendConnected(false);
    }
  }, [setBackendConnected]);

  // Initialize System
  useEffect(() => {
    const initialize = async () => {
      try {
        // Simulate boot sequence for visual effect
        bootIntervalRef.current = setInterval(() => {
          setBootProgress(prev => {
            if (prev >= 100) {
              if (bootIntervalRef.current) {
                clearInterval(bootIntervalRef.current);
                bootIntervalRef.current = null;
              }
              return 100;
            }
            return prev + 10;
          });
        }, 100);

        // Initialize hardware and session
        await initSystem();
        await checkSession();
        
        // Start backend health monitoring
        await checkBackendHealth();
        healthIntervalRef.current = setInterval(checkBackendHealth, 5000);

        // Complete boot sequence
        setTimeout(() => {
          setIsBooting(false);
        }, 1500);
      } catch (error: any) {
        console.error('Initialization failed:', error);
        setInitError(error.message || 'Failed to initialize system');
        setIsBooting(false);
      }
    };

    initialize();

    // Cleanup on unmount
    return () => {
      if (bootIntervalRef.current) {
        clearInterval(bootIntervalRef.current);
      }
      if (healthIntervalRef.current) {
        clearInterval(healthIntervalRef.current);
      }
    };
  }, [initSystem, checkSession, checkBackendHealth]);

  // Hash Change Listener for Multi-Window Routing
  useEffect(() => {
    const handleHashChange = () => setCurrentRoute(window.location.hash);
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Retry Handler
  const handleRetry = useCallback(async () => {
    setInitError(null);
    setIsBooting(true);
    setBootProgress(0);
    
    try {
      await initSystem();
      await checkSession();
      await checkBackendHealth();
      setIsBooting(false);
    } catch (error: any) {
      setInitError(error.message || 'Failed to initialize system');
      setIsBooting(false);
    }
  }, [initSystem, checkSession, checkBackendHealth]);

  // Render Boot Screen
  if (isBooting) {
    return (
      <>
        <Starfield opacity={0.3} threatLevel={threatLevel} />
        <BootScreen progress={bootProgress} />
      </>
    );
  }

  // Render Error Boundary
  if (initError) {
    return (
      <>
        <Starfield opacity={0.3} threatLevel={threatLevel} />
        <ErrorBoundary error={initError} onRetry={handleRetry} />
      </>
    );
  }

  // ROUTING LOGIC: Bubble Window (Passive Mode)
  if (currentRoute === '#/bubble') {
    return (
      <>
        <Starfield opacity={0.15} threatLevel={threatLevel} />
        <ConnectionStatus connected={backendConnected} />
        <PassiveBubble />
      </>
    );
  }

  // MAIN WINDOW ROUTING: Zero Trust Gate
  return (
    <>
      <Starfield opacity={0.4} threatLevel={threatLevel} />
      <ConnectionStatus connected={backendConnected} />
      {user ? <Dashboard /> : <AuthScreen />}
    </>
  );
}