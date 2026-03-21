import { useState } from 'react';
import { useSystemStore } from '../../store/systemStore';
import { Zap, Activity, AlertTriangle } from 'lucide-react';

export default function ModeToggle() {
  const { mode, toggleMode, systemVRAM } = useSystemStore();
  const [isThundering, setIsThundering] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  
  const hasEnoughVram = systemVRAM >= 6144;
  const isPassive = mode === 'passive';

  const handleToggle = async () => {
    if (!hasEnoughVram || isToggling) return;
    
    setIsThundering(true);
    setIsToggling(true);
    
    try {
      await toggleMode();
      setTimeout(() => setIsThundering(false), 500);
    } catch (error) {
      console.error('Mode toggle failed:', error);
      setIsThundering(false);
    } finally {
      setIsToggling(false);
    }
  };

  const baseClasses = "relative flex items-center gap-2 px-4 py-1.5 rounded border transition-all duration-300 font-bold tracking-wider text-xs";
  const colorClasses = isPassive 
    ? "border-[#bc13fe] text-[#bc13fe] bg-[#bc13fe]/10 shadow-[0_0_15px_rgba(188,19,254,0.3)]" 
    : "border-[#00f3ff] text-[#00f3ff] bg-[#00f3ff]/10 shadow-[0_0_15px_rgba(0,243,255,0.2)]";
  const disabledClasses = !hasEnoughVram ? "opacity-50 cursor-not-allowed grayscale" : "hover:bg-opacity-20 hover:scale-105";
  const loadingClasses = isToggling ? "opacity-70 cursor-wait" : "";
  const animationClasses = isThundering ? "animate-thunder" : "";

  return (
    <button 
      onClick={handleToggle}
      disabled={!hasEnoughVram || isToggling}
      style={{ '--current-color': isPassive ? '#bc13fe' : '#00f3ff' } as React.CSSProperties}
      className={`${baseClasses} ${colorClasses} ${disabledClasses} ${loadingClasses} ${animationClasses}`}
      aria-label={`Switch to ${isPassive ? 'Active' : 'Passive'} mode`}
      title={!hasEnoughVram ? 'Requires 6GB+ VRAM' : `Current mode: ${isPassive ? 'Passive' : 'Active'}`}
    >
      {isToggling ? (
        <Activity size={16} className="animate-spin" />
      ) : isPassive ? (
        <Activity size={16} />
      ) : (
        <Zap size={16} />
      )}
      <span>
        {isToggling ? 'SWITCHING...' : isPassive ? 'PASSIVE [MONITORING]' : 'ACTIVE [CHAT ONLY]'}
      </span>
      {!hasEnoughVram && (
        <AlertTriangle size={12} className="text-red-500" />
      )}
    </button>
  );
}