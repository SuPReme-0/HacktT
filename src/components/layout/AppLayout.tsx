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
  isBackendConnected?: boolean;
}

export default function AppLayout({ 
  children, 
  showSidebar = true, 
  showHeader = true 
}: AppLayoutProps) {
  const { threatLevel, mode, isSidebarOpen } = useSystemStore();

  return (
    <div className="relative w-screen h-screen bg-[#030305] text-white overflow-hidden font-mono">
      {/* 1. Background (Persistent) */}
      <Starfield opacity={0.4} threatLevel={threatLevel} mode={mode} />

      {/* 2. Connection Status (Always Visible) */}
      <ConnectionStatus />

      {/* 3. Header (Conditional) */}
      {showHeader && <Header />}

      {/* 4. Main Content Area */}
      <div className="flex pt-16 h-full z-10 relative">
        {/* Sidebar (Conditional) */}
        {showSidebar && isSidebarOpen && <Sidebar />}

        {/* Page Content */}
        <main className="flex-1 flex flex-col relative overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}