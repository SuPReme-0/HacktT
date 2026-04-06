import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { useSystemStore } from './store/systemStore';

// Components
import AppLayout from './components/layout/AppLayout';
import AuthScreen from './components/auth/AuthScreen';
import DashboardView from './components/views/DashboardView';
import PassiveBubble from './components/views/PassiveBubble';
import BootScreen from './components/feedback/BootScreen';
import ErrorBoundary from './components/feedback/ErrorBoundary';
import FirstRunSetup from './components/setup/FirstRunSetup'; // <-- NEW: Setup Wizard

// Hooks
import useBootSequence from './hooks/useBootSequence';
import useBackendHealth from './hooks/useBackendHealth';

export default function App() {
  const { user, threatLevel, initSystem, checkSession } = useSystemStore();
  const { isBooting, bootProgress, initError, handleRetry } = useBootSequence(initSystem, checkSession);
  const { backendConnected } = useBackendHealth(); 
  
  const [currentRoute, setCurrentRoute] = useState<string>(window.location.hash);

  useEffect(() => {
    // 1. Listen for hash-based navigation changes
    const handleHashChange = () => setCurrentRoute(window.location.hash);
    window.addEventListener('hashchange', handleHashChange);
    
    // 2. Dismiss the OS-level Splash Screen
    // We add a tiny 500ms delay to ensure the React DOM has actually painted to the screen 
    // before dropping the splash screen, preventing any white flashes.
    setTimeout(() => {
      invoke('close_splashscreen').catch(console.error);
    }, 500);

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // ==========================================================================
  // WINDOW & ROUTE INTERCEPTORS (Must happen BEFORE Boot Sequence)
  // ==========================================================================
  
  // A. The First-Run Installer Wizard
  // Bypasses boot sequence because the models don't exist yet!
  if (currentRoute === '#/setup') {
    return <FirstRunSetup />;
  }

  // B. The Floating Sentinel Widget
  // Bypasses standard layout to maintain 100% OS-level window transparency
  if (currentRoute === '#/bubble') {
    return <PassiveBubble isBackendConnected={backendConnected} />;
  }

  // ==========================================================================
  // MAIN DASHBOARD LIFECYCLE
  // ==========================================================================

  // 1. HARDWARE INIT SEQUENCE
  if (isBooting) {
    return <BootScreen progress={bootProgress} threatLevel={threatLevel} />;
  }

  // 2. CRITICAL FAILURE STATE
  if (initError) {
    return <ErrorBoundary error={initError} onRetry={handleRetry} threatLevel={threatLevel} />;
  }

  // 3. MAIN DASHBOARD ROUTING (Zero-Trust Gate)
  return (
    // AppLayout will display a persistent warning banner if Python connection is lost
    <AppLayout isBackendConnected={backendConnected}>
      {user ? <DashboardView /> : <AuthScreen />}
    </AppLayout>
  );
}