import { useSystemStore } from '../../store/systemStore';
import ModeToggle from '../ui/ModeToggle';
import Avatar from '../ui/Avatar';

export default function Header() {
  const { toggleSidebar, user } = useSystemStore();
  const isSidebarOpen = useSystemStore.getState().isSidebarOpen;

  return (
    <header className="absolute top-0 w-full h-16 border-b border-white/10 bg-[#030305]/80 backdrop-blur-md flex items-center justify-between px-6 z-20">
      <div className="flex items-center gap-4">
        <button 
          onClick={toggleSidebar} 
          className="text-white/50 hover:text-white transition"
        >
          {isSidebarOpen ? '✕' : '☰'}
        </button>
        <h1 className="text-xl tracking-[0.2em] font-bold">
          HACKT<span className="text-cyan-400">.OS</span>
        </h1>
      </div>

      <div className="flex items-center gap-6">
        <ModeToggle />
        {user && (
          <Avatar name={user.name} src={user.avatarUrl} size="sm" />
        )}
      </div>
    </header>
  );
}