import { useSystemStore } from '../../store/systemStore';
import Card from '../ui/Card';
import Badge from '../ui/Badge';
import Divider from '../ui/Divider';

export default function Sidebar() {
  // ✅ Correctly subscribed using individual selectors
  const vaultSkills = useSystemStore((state) => state.vaultSkills);
  const telemetryData = useSystemStore((state) => state.telemetryData);
  const sessions = useSystemStore((state) => state.sessions || []); // Assuming sessions are added to store

  return (
    <aside className="w-80 md:w-80 border-r border-white/10 bg-[#050505]/90 backdrop-blur-xl overflow-y-auto gloomy-scroll z-10 hidden md:block">
      <div className="p-4 space-y-6">

        {/* Active Sessions */}
        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">Active Sessions</h3>
          <div className="space-y-2">
            {sessions.slice(0, 3).map((session: any) => (
              <Card key={session.id} hoverable className="p-3 cursor-pointer hover:border-[#00f3ff]/50 transition-colors">
                <div className="text-sm text-cyan-100 truncate">{session.title || 'Untitled Session'}</div>
                <div className="text-xs text-white/40 mt-1">
                  {new Date(session.updated_at).toLocaleTimeString()}
                </div>
              </Card>
            ))}
          </div>
        </div>

        <Divider />

        {/* Security Discoveries */}
        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">Security Discoveries</h3>
          <Card variant="red" className="p-3">
            <div className="text-sm text-red-200">Phishing Pattern Detected</div>
            <div className="text-xs text-white/40 mt-1">Vault Ref: SEC-004</div>
          </Card>
        </div>

        <Divider />

        {/* Vault Skills */}
        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">Vault Skills</h3>
          <div className="flex flex-wrap gap-2">
            {/* ✅ Optional chaining + unique key */}
            {vaultSkills?.slice(0, 4).map((skill) => (
              <Badge key={skill.chapter} variant="purple" size="sm">
                {skill.chapter}
              </Badge>
            ))}
          </div>
        </div>

        <Divider />

        {/* System Telemetry */}
        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">System Telemetry</h3>
          <div className="space-y-2 text-xs text-gray-400">
            <div className="flex justify-between">
              <span>CPU</span>
              <span className="text-cyan-400">{telemetryData?.cpuUsage ?? 0}%</span>
            </div>
            <div className="flex justify-between">
              <span>Memory</span>
              <span className="text-cyan-400">{telemetryData?.memoryUsage ?? 0}%</span>
            </div>
            <div className="flex justify-between">
              <span>Threats</span>
              <span className="text-red-400">{telemetryData?.threatsDetected ?? 0}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}