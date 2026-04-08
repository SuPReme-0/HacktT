import React from 'react';
import { useSystemStore } from '../../store/systemStore';
import Starfield from './Starfield';
import Header from './Header';
import Sidebar from './Sidebar';
import ConnectionStatus from '../feedback/ConnectionStatus';

interface AppLayoutProps {
  children: React.ReactNode;
  showSidebar?: boolean;
  showHeader?: boolean;
}

export default function AppLayout({ 
  children, 
  showSidebar = true, 
  showHeader = true 
}: AppLayoutProps) {
  const threatLevel = useSystemStore((state) => state.threatLevel);
  const mode = useSystemStore((state) => state.mode);
  const isSidebarOpen = useSystemStore((state) => state.isSidebarOpen);
  const backendConnected = useSystemStore((state) => state.backendConnected); // ✅ Added backendConnected from store

  // Dynamic threat-based background glow
  const getThreatGlow = () => {
    switch (threatLevel) {
      case 'critical': return 'shadow-[0_0_100px_rgba(255,0,60,0.3)]';
      case 'high': return 'shadow-[0_0_60px_rgba(255,0,60,0.2)]';
      case 'medium': return 'shadow-[0_0_30px_rgba(255,176,0,0.15)]';
      case 'safe': return 'shadow-[0_0_10px_rgba(0,255,100,0.1)]';
      default: return '';
    }
  };

  return (
    <div className={`relative w-screen h-screen bg-[#030305] text-white overflow-hidden font-mono transition-shadow duration-500 ${getThreatGlow()}`}>
      {/* 1. Background (Persistent) */}
      <Starfield opacity={0.4} threatLevel={threatLevel} mode={mode} />

      {/* 2. Connection Status (Always Visible, Top-Right) */}
      <ConnectionStatus />

      {/* 3. Header (Conditional) */}
      {showHeader && <Header />}

      {/* 4. Main Content Area */}
      <div className="flex pt-16 h-full z-10 relative">
        {/* Sidebar (Conditional + Responsive) */}
        {showSidebar && isSidebarOpen && (
          <div className="hidden md:block">
            <Sidebar />
          </div>
        )}

        {/* Page Content */}
        <main className="flex-1 flex flex-col relative overflow-hidden">
          {children}
        </main>
      </div>
      
      {/* 5. Backend Connection Warning Banner (Conditional) */}
      {!backendConnected && (
        <div className="absolute bottom-0 left-0 right-0 bg-red-900/20 border-t border-red-500/30 text-red-400 text-xs py-2 px-4 text-center animate-pulse">
          ⚠️ Backend disconnected. Some features may be unavailable.
        </div>
      )}
    </div>
  );
}