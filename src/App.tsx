import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { writeTextFile } from '@tauri-apps/api/fs'; // ✅ Added for file writing
import { useSystemStore } from './store/systemStore';

// Components
import AppLayout from './components/layout/AppLayout';
import AuthScreen from './components/auth/AuthScreen';
import DashboardView from './components/views/DashboardView';
import PassiveBubble from './components/views/PassiveBubble';
import BootScreen from './components/feedback/BootScreen';
import ErrorBoundary from './components/feedback/ErrorBoundary';
import FirstRunSetup from './components/setup/FirstRunSetup';
import CodeDiffModal from './components/views/CodeDiffModal'; 

// Hooks
import useBootSequence from './hooks/useBootSequence';
import useBackendHealth from './hooks/useBackendHealth';

// Route constants for maintainability
const ROUTES = {
  SETUP: '#/setup',
  BUBBLE: '#/bubble',
  DASHBOARD: '#/',
} as const;

export default function App() {
  const { user, threatLevel, initSystem, checkSession } = useSystemStore();
  const { isBooting, bootProgress, initError, handleRetry } = useBootSequence(
    initSystem, 
    checkSession,
    45000 // 45 second timeout for model loading
  );
  useBackendHealth(10000); // Check backend health every 10 seconds
  
  const [currentRoute, setCurrentRoute] = useState<string>(window.location.hash);
  const [showDiffModal, setShowDiffModal] = useState<boolean>(false);
  const [diffData, setDiffData] = useState<any>(null);

  // ======================================================================
  // 1. ROUTE & SPLASH SCREEN MANAGEMENT
  // ======================================================================
  useEffect(() => {
    const handleHashChange = () => setCurrentRoute(window.location.hash);
    window.addEventListener('hashchange', handleHashChange);
    
    const splashTimeout = setTimeout(() => {
      invoke('close_splashscreen').catch(console.warn);
    }, 500);

    // Listen for Code Diff events from backend
    let unlistenDiff: (() => void) | undefined;
    
    const setupDiffListener = async () => {
      try {
        const { listen } = await import('@tauri-apps/api/event');
        return await listen('code_diff_available', (event: any) => {
          setDiffData(event.payload?.data);
          setShowDiffModal(true);
        });
      } catch (error) {
        console.warn('Failed to setup diff listener:', error);
        return () => {};
      }
    };
    
    setupDiffListener().then(unlisten => {
      unlistenDiff = unlisten;
    });

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
      clearTimeout(splashTimeout);
      if (unlistenDiff) unlistenDiff();
    };
  }, []);

  // ======================================================================
  // 2. GLOBAL APPLY FIX LOGIC
  // ======================================================================
  // ✅ FIX: Implemented the missing onApply prop
  const handleApplyFix = async () => {
    if (!diffData) return;
    try {
      // Strip 'ide:' or 'browser:' tags sent by the backend telemetry
      const cleanPath = diffData.source.replace(/^(ide|browser):/, '');
      await writeTextFile(cleanPath, diffData.suggested_fix);
      
      console.log(`✅ Global fix applied to ${cleanPath}`);
      setShowDiffModal(false);
      setDiffData(null);
    } catch (error) {
      console.error("Failed to write fix to disk from root:", error);
    }
  };

  // ======================================================================
  // 3. ROUTE INTERCEPTORS (Highest Priority)
  // ======================================================================
  if (currentRoute === ROUTES.SETUP) {
    return <FirstRunSetup />;
  }

  if (currentRoute === ROUTES.BUBBLE) {
    return <PassiveBubble />;
  }

  // ======================================================================
  // 4. MAIN DASHBOARD LIFECYCLE
  // ======================================================================
  if (isBooting) {
    return <BootScreen 
      progress={bootProgress} 
      threatLevel={threatLevel}
      onBootComplete={() => {}}
    />;
  }

  if (initError) {
    return <ErrorBoundary 
      error={initError} 
      onRetry={handleRetry} 
      threatLevel={threatLevel}
    />;
  }

  // E. MAIN DASHBOARD ROUTING
  return (
    <>
      <AppLayout 
        showSidebar={true}
        showHeader={true}
      >
        {user ? <DashboardView /> : <AuthScreen />}
      </AppLayout>
      
      {/* Code Diff Modal (Triggered globally) */}
      {showDiffModal && diffData && (
        <CodeDiffModal
          isOpen={showDiffModal}
          onClose={() => setShowDiffModal(false)}
          onApply={handleApplyFix} // ✅ FIX: Missing prop added
          originalCode={diffData.original_code}
          suggestedFix={diffData.suggested_fix}
          threatLevel={diffData.threat_level}
          source={diffData.source}
          vulnerability={diffData.vulnerability}
        />
      )}
    </>
  );
}