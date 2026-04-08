import { useSystemStore } from '../../store/systemStore';
import ModeToggle from '../ui/ModeToggle';
import Avatar from '../ui/Avatar';

export default function Header() {
  const toggleSidebar = useSystemStore((state) => state.toggleSidebar);
  const user = useSystemStore((state) => state.user);
  const isSidebarOpen = useSystemStore((state) => state.isSidebarOpen);
  const threatLevel = useSystemStore((state) => state.threatLevel);

  // Dynamic threat-based header styling
  const getThreatStyles = () => {
    switch (threatLevel) {
      case 'critical':
        return {
          shadow: 'shadow-[0_0_100px_rgba(255,0,60,0.3)]',
          border: 'border-[#ff003c]/50',
          glow: 'animate-pulse'
        };
      case 'high':
        return {
          shadow: 'shadow-[0_0_60px_rgba(255,0,60,0.2)]',
          border: 'border-[#ff003c]/30',
          glow: ''
        };
      case 'medium':
        return {
          shadow: 'shadow-[0_0_30px_rgba(255,176,0,0.15)]',
          border: 'border-[#ffb000]/30',
          glow: ''
        };
      default: // 'safe'
        return {
          shadow: 'shadow-[0_0_10px_rgba(0,255,100,0.1)]',
          border: 'border-white/10',
          glow: ''
        };
    }
  };

  const threatStyles = getThreatStyles();

  return (
    <header 
      className={`absolute top-0 w-full h-16 ${threatStyles.shadow} bg-[#030305]/80 backdrop-blur-md flex items-center justify-between px-4 md:px-6 z-20 transition-all duration-300 border-b ${threatStyles.border}`}
      data-tauri-drag-region // ✅ Enables native window dragging
    >
      {/* Background: Dashboard Header Asset (Landscape) */}
      <div 
        className="absolute inset-0 opacity-10 pointer-events-none"
        style={{
          backgroundImage: 'url(/dashboard-header.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }}
        aria-hidden="true"
      />
      
      {/* Gradient Overlay for Readability */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#030305]/90 via-[#030305]/70 to-transparent pointer-events-none" aria-hidden="true" />

      {/* Left: Sidebar Toggle + Branding */}
      <div className="flex items-center gap-4 relative z-10">
        <button 
          onClick={toggleSidebar} 
          className="p-2 text-white/50 hover:text-white transition focus:outline-none focus:ring-2 focus:ring-[#00f3ff] focus:ring-offset-2 focus:ring-offset-[#030305] rounded-lg"
          aria-label={isSidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          aria-expanded={isSidebarOpen}
        >
          {isSidebarOpen ? '✕' : '☰'}
        </button>
        <h1 className="text-lg md:text-xl tracking-[0.2em] font-bold text-white drop-shadow-[0_0_8px_rgba(0,243,255,0.5)]">
          HACKT<span className="text-[#00f3ff]">.OS</span>
        </h1>
      </div>

      {/* Right: Mode Toggle + User Profile */}
      <div className="flex items-center gap-4 md:gap-6 relative z-10">
        <ModeToggle />
        {user && (
          <Avatar name={user.name} src={user.avatarUrl} size="sm" />
        )}
      </div>

      {/* Threat Level Indicator (Bottom Border Glow) */}
      <div 
        className={`absolute bottom-0 left-0 right-0 h-0.5 ${threatStyles.glow}`}
        style={{
          background: threatLevel === 'critical' ? 'linear-gradient(90deg, transparent, #ff003c, transparent)' :
                     threatLevel === 'high' ? 'linear-gradient(90deg, transparent, #ff003c, transparent)' :
                     threatLevel === 'medium' ? 'linear-gradient(90deg, transparent, #ffb000, transparent)' :
                     'linear-gradient(90deg, transparent, #00ff88, transparent)'
        }}
        aria-hidden="true"
      />
    </header>
  );
}