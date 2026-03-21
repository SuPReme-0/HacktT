import { useEffect, useState } from 'react';
import { useSystemStore } from './store/systemStore';
import AppLayout from './components/layout/AppLayout';
import AuthScreen from './components/auth/AuthScreen';
import DashboardView from './components/views/DashboardView';
import PassiveBubble from './components/views/PassiveBubble';
import BootScreen from './components/feedback/BootScreen';
import ErrorBoundary from './components/feedback/ErrorBoundary';
import useBootSequence from './hooks/useBootSequence';
import useBackendHealth from './hooks/useBackendHealth';

export default function App() {
  // FIXED: Extract initSystem and checkSession from the store
  const { user, threatLevel, initSystem, checkSession } = useSystemStore();
  
  // FIXED: Pass them into the hook
  const { isBooting, bootProgress, initError, handleRetry } = useBootSequence(initSystem, checkSession);
  
  const { backendConnected } = useBackendHealth(); 
  const [currentRoute, setCurrentRoute] = useState<string>(window.location.hash);

  useEffect(() => {
    const handleHashChange = () => setCurrentRoute(window.location.hash);
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // 1. HARDWARE INIT SEQUENCE
  if (isBooting) {
    return <BootScreen progress={bootProgress} threatLevel={threatLevel} />;
  }

  // 2. CRITICAL FAILURE STATE
  if (initError) {
    return <ErrorBoundary error={initError} onRetry={handleRetry} threatLevel={threatLevel} />;
  }

  // 3. TAURI MULTI-WINDOW ROUTING: The Passive Bubble
  // UPGRADE: Removed AppLayout to ensure 100% OS-level window transparency
  if (currentRoute === '#/bubble') {
    return <PassiveBubble />;
  }

  // 4. MAIN DASHBOARD ROUTING (Zero-Trust Gate)
  return (
    // Pass backend status to the layout to display a warning banner if Python dies
    <AppLayout isBackendConnected={backendConnected}>
      {user ? <DashboardView /> : <AuthScreen />}
    </AppLayout>
  );
}