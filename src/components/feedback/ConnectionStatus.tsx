import { useSystemStore } from '../../store/systemStore';

export default function ConnectionStatus() {
  const backendConnected = useSystemStore((state) => state.backendConnected);

  return (
    <div className="fixed top-4 right-4 z-40 flex items-center gap-2 px-3 py-1.5 rounded-full 
                    bg-[#0a0a0a]/80 border border-[#1f1f1f] backdrop-blur-sm">
      <div className={`w-2 h-2 rounded-full ${
        backendConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
      }`} />
      <span className="text-[8px] text-gray-400 uppercase tracking-widest">
        {backendConnected ? 'Core Online' : 'Core Offline'}
      </span>
    </div>
  );
}