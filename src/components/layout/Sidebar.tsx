import { useSystemStore } from '../../store/systemStore';
import Card from '../ui/Card';
import Badge from '../ui/Badge';
import Divider from '../ui/Divider';

export default function Sidebar() {
  const { vaultSkills, telemetryData } = useSystemStore();

  return (
    <aside className="w-80 border-r border-white/10 bg-[#050505]/90 backdrop-blur-xl overflow-y-auto gloomy-scroll z-10">
      <div className="p-4 space-y-6">
        
        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">Projects</h3>
          <div className="space-y-2">
            <Card hoverable className="p-3">
              <div className="text-sm text-cyan-100">Operation: BlackWall</div>
              <div className="text-xs text-white/40 mt-1">Created 2h ago</div>
            </Card>
          </div>
        </div>

        <Divider />

        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">Security Discoveries</h3>
          <Card variant="red" className="p-3">
            <div className="text-sm text-red-200">Phishing Pattern Detected</div>
            <div className="text-xs text-white/40 mt-1">Vault Ref: SEC-004</div>
          </Card>
        </div>

        <Divider />

        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">Vault Skills</h3>
          <div className="flex flex-wrap gap-2">
            {vaultSkills.slice(0, 4).map((skill, i) => (
              <Badge key={i} variant="purple" size="sm">
                {skill.chapter}
              </Badge>
            ))}
          </div>
        </div>

        <Divider />

        <div>
          <h3 className="text-xs text-white/40 uppercase tracking-widest mb-3">System Telemetry</h3>
          <div className="space-y-2 text-xs text-gray-400">
            <div className="flex justify-between">
              <span>CPU</span>
              <span className="text-cyan-400">{telemetryData.cpuUsage}%</span>
            </div>
            <div className="flex justify-between">
              <span>Memory</span>
              <span className="text-cyan-400">{telemetryData.memoryUsage}%</span>
            </div>
            <div className="flex justify-between">
              <span>Threats</span>
              <span className="text-red-400">{telemetryData.threatsDetected}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}