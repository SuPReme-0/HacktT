import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/tauri';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import { WebviewWindow } from '@tauri-apps/api/window';

// ======================================================================
// 1. CONSTANTS & TYPE DEFINITIONS
// ======================================================================
const API_BASE = import.meta.env.PROD 
  ? 'http://127.0.0.1:8000' 
  : 'http://localhost:8000';
const LOCAL_STORAGE_KEY = 'HACKT_SOVEREIGN_OPERATOR';

export interface User {
  name: string;
  avatarUrl: string;
  role: 'operator';
}

export interface Message {
  id: string;
  sender: 'user' | 'ai' | 'system';
  text: string;
  timestamp: Date;
}

export interface Permissions {
  micEnabled: boolean;
  visionEnabled: boolean;
  ideIntegration: boolean;
  browserIntegration: boolean;
  cloudSync: boolean;
}

export interface VaultSkill {
  chapter: string;
  topicsCovered: string[];
}

export interface ActiveContext {
  file?: string;
  language?: string;
  lastModified?: string;
  recentChanges?: string[];
}

export interface TelemetryData {
  scansCompleted: number;
  threatsDetected: number;
  lastScanTime: string;
  activeConnections: number;
  cpuUsage: number;
  memoryUsage: number;
}

export interface Session {
  id: string;
  title: string;
  updated_at: string;
}

// ======================================================================
// 2. SYSTEM STATE INTERFACE
// ======================================================================
interface SystemState {
  // Identity
  user: User | null;
  setUser: (user: User | null) => void;
  loginLocal: (name: string, avatarDataUrl?: string) => Promise<void>;
  checkSession: () => Promise<void>;
  logout: () => Promise<void>;
  
  // Hardware & Network
  systemVRAM: number;
  setSystemVRAM: (vram: number) => void;
  idePort: number;
  browserPort: number;
  initSystem: () => Promise<void | (() => void)>;
  
  // Operational Modes
  mode: 'active' | 'passive';
  isProcessing: boolean;
  isSpeaking: boolean;
  setIsSpeaking: (val: boolean) => void;
  threatLevel: 'safe' | 'medium' | 'high' | 'critical';
  vaultSkills: VaultSkill[];
  toggleMode: () => Promise<void>;
  
  // Permissions
  permissions: Permissions;
  togglePermission: (key: keyof Permissions) => Promise<void>;
  
  // Chat Interface
  messages: Message[];
  sendMessage: (text: string) => Promise<void>;
  
  // IDE Context & Telemetry
  activeContext: ActiveContext;
  setActiveContext: (context: ActiveContext) => void;
  telemetryData: TelemetryData;
  setTelemetryData: (data: Partial<TelemetryData>) => void;
  
  // Backend Connection
  backendConnected: boolean;
  setBackendConnected: (connected: boolean) => void;
  checkBackendHealth: () => Promise<void>;
  
  // UI State & Session
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  session_id: string;
  generateSessionId: () => Promise<void>;
  
  // Sessions Management
  sessions: Session[];
  setSessions: (sessions: Session[]) => void;
  addSession: (session: Session) => void;
  removeSession: (sessionId: string) => void;
}

// ======================================================================
// 3. ZUSTAND STORE IMPLEMENTATION
// ======================================================================
export const useSystemStore = create<SystemState>((set, get) => ({
  // ------------------------------------------------------------------
  // IDENTITY (LOCAL DB)
  // ------------------------------------------------------------------
  user: null,
  setUser: (user) => set({ user }),
  
  loginLocal: async (name: string, avatarDataUrl?: string) => {
    const fallbackAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`;
    const operator: User = { name, avatarUrl: avatarDataUrl || fallbackAvatar, role: 'operator' };
    
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(operator));
    set({ user: operator });
  },
  
  checkSession: async () => {
    const savedOperator = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (savedOperator) {
      try {
        set({ user: JSON.parse(savedOperator) });
      } catch {
        localStorage.removeItem(LOCAL_STORAGE_KEY);
      }
    }
  },
  
  logout: async () => {
    localStorage.removeItem(LOCAL_STORAGE_KEY);
    set({ user: null, messages: [], activeContext: {}, sessions: [] });
  },
  
  // ------------------------------------------------------------------
  // HARDWARE & NETWORK
  // ------------------------------------------------------------------
  systemVRAM: 0,
  setSystemVRAM: (vram) => set({ systemVRAM: vram }),
  idePort: 8081,
  browserPort: 8082,
  
  initSystem: async () => {
    let unlistenTelemetry: UnlistenFn | undefined;
    
    try {
      // 1. Generate local session ID via Rust OS layer
      const sessionId = await invoke<string>('generate_new_session').catch(() => `session-${Date.now()}`);
      set({ session_id: sessionId });
      
      // 2. Unified Telemetry Listener (Backend emits type: "threat", "context", "telemetry")
      unlistenTelemetry = await listen('telemetry', (event: any) => {
        const payload = event.payload;
        
        // Handle threat alerts
        if (payload?.type === 'threat') {
          set((state) => ({ 
            threatLevel: (payload.level as 'safe' | 'medium' | 'high' | 'critical') || 'medium',
            telemetryData: {
              ...state.telemetryData,
              threatsDetected: state.telemetryData.threatsDetected + 1,
              lastScanTime: new Date().toLocaleTimeString()
            }
          }));
        }
        
        // Handle IDE context updates
        if (payload?.type === 'context') {
          set({ activeContext: payload as ActiveContext });
        }
        
        // Handle general telemetry updates
        if (payload?.type === 'telemetry') {
          set((state) => ({
            telemetryData: {
              ...state.telemetryData,
              cpuUsage: payload.cpu_usage || state.telemetryData.cpuUsage,
              memoryUsage: payload.memory_usage || state.telemetryData.memoryUsage,
              lastScanTime: new Date().toLocaleTimeString()
            }
          }));
        }
      });
      
      // 3. Initial Health Check & Fetch Sessions
      await get().checkBackendHealth();
      
      // 4. Fetch sessions from backend if available
      try {
        const response = await fetch(`${API_BASE}/api/system/sessions`);
        if (response.ok) {
          const data = await response.json();
          if (data.sessions) {
            set({ sessions: data.sessions });
          }
        }
      } catch (error) {
        console.warn('Failed to fetch sessions:', error);
      }
      
    } catch (error: any) {
      console.warn('System listener initialization failed:', error.message);
    }
    
    return () => {
      unlistenTelemetry?.();
    };
  },
  
  // ------------------------------------------------------------------
  // OPERATIONAL MODES
  // ------------------------------------------------------------------
  mode: 'active',
  isProcessing: false,
  isSpeaking: false,
  setIsSpeaking: (val) => set({ isSpeaking: val }),
  threatLevel: 'safe',
  vaultSkills: [
    { chapter: 'Network Forensics', topicsCovered: ['Wireshark', 'Packet Sniffing'] },
    { chapter: 'Web Exploitation', topicsCovered: ['XSS', 'SQLi', 'CSRF'] },
    { chapter: 'Binary Analysis', topicsCovered: ['Reverse Engineering', 'Malware Analysis'] },
    { chapter: 'Cloud Security', topicsCovered: ['AWS Security', 'Azure Security'] }
  ],
  
  toggleMode: async () => {
    const { mode, systemVRAM } = get();
    
    if (mode === 'active' && systemVRAM < 6144) {
      throw new Error('Insufficient VRAM for Passive Mode (6GB required)');
    }
    
    const newMode = mode === 'active' ? 'passive' : 'active';
    
    try {
      // Notify Python backend
      fetch(`${API_BASE}/api/system/mode`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ mode: newMode })
      }).catch(console.warn);

      // Native Tauri Bubble Control
      const bubbleWindow = WebviewWindow.getByLabel('bubble');
      if (bubbleWindow) {
        if (newMode === 'passive') {
          await bubbleWindow.show();
          await bubbleWindow.setAlwaysOnTop(true);
        } else {
          await bubbleWindow.hide();
        }
      }
      
      set({ mode: newMode });
    } catch (error: any) {
      console.error('Mode toggle failed:', error.message);
      throw error;
    }
  },
  
  // ------------------------------------------------------------------
  // PERMISSIONS MATRIX
  // ------------------------------------------------------------------
  permissions: {
    micEnabled: false,
    visionEnabled: false,
    ideIntegration: false,
    browserIntegration: false,
    cloudSync: false,
  },
  
  togglePermission: async (key: keyof Permissions) => {
    const { permissions, idePort, systemVRAM } = get();
    const isNowEnabled = !permissions[key];
    
    if (key === 'visionEnabled' && isNowEnabled && systemVRAM < 6144) {
      throw new Error('Insufficient VRAM for Vision (6GB required)');
    }
    
    try {
      if (key === 'ideIntegration') {
        fetch(`${API_BASE}/api/config/ide`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ enabled: isNowEnabled, port: idePort })
        }).catch(console.warn);
      } else if (key === 'visionEnabled') {
        const action = isNowEnabled ? 'start_vision' : 'stop_vision';
        await invoke(action).catch(console.warn);
      } else if (key === 'micEnabled') {
        const action = isNowEnabled ? 'start_mic' : 'stop_mic';
        await invoke(action).catch(console.warn);
      }
      
      set((state) => ({
        permissions: { ...state.permissions, [key]: isNowEnabled }
      }));
    } catch (error: any) {
      console.error(`Permission toggle failed for ${key}:`, error.message);
      throw error;
    }
  },
  
  // ------------------------------------------------------------------
  // CHAT INTERFACE (Stream-Safe)
  // ------------------------------------------------------------------
  messages: [
    { 
      id: 'system-init', 
      sender: 'system', 
      text: 'Sovereign Vault online. Disconnected from external networks. Awaiting commands.', 
      timestamp: new Date() 
    }
  ],
  
  sendMessage: async (text: string) => {
    const { mode, session_id } = get();
    
    // 🛡️ CRITICAL: Unique IDs prevent React mapping collisions
    const userMsgId = `usr-${Date.now()}`;
    const aiMsgId = `ai-${Date.now() + 1}`;
    
    set((state) => ({
      messages: [
        ...state.messages, 
        { id: userMsgId, sender: 'user', text, timestamp: new Date() },
        { id: aiMsgId, sender: 'ai', text: '', timestamp: new Date() } // Inject empty AI message
      ],
      isProcessing: true
    }));
    
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, mode, session_id })
      });
      
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      if (!response.body) throw new Error('No stream body found in response');
      
      const reader = response.body.getReader();
      // 🛡️ utf-8 explicit definition
      const decoder = new TextDecoder('utf-8');
      let aiText = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        // 🛡️ CRITICAL: { stream: true } prevents multi-byte character splitting bugs
        aiText += decoder.decode(value, { stream: true });
        
        set((state) => ({
          messages: state.messages.map(m => 
            m.id === aiMsgId ? { ...m, text: aiText } : m
          )
        }));
      }
      
      // Flush the remaining bytes
      aiText += decoder.decode();
      set((state) => ({
        messages: state.messages.map(m => 
          m.id === aiMsgId ? { ...m, text: aiText } : m
        ),
        isProcessing: false
      }));
      
    } catch (error: any) {
      set((state) => ({
        messages: [
          ...state.messages.filter(m => m.id !== aiMsgId), // Remove empty placeholder
          {
            id: `err-${Date.now()}`,
            sender: 'system',
            text: `[ERROR]: Failed to connect to AI Core on Port 8000. ${error.message}`,
            timestamp: new Date()
          }
        ],
        isProcessing: false
      }));
    }
  },
  
  // ------------------------------------------------------------------
  // BACKEND CONNECTION & HEALTH
  // ------------------------------------------------------------------
  activeContext: {},
  setActiveContext: (context) => set({ activeContext: context }),
  
  telemetryData: {
    scansCompleted: 0,
    threatsDetected: 0,
    lastScanTime: 'Never',
    activeConnections: 0,
    cpuUsage: 0,
    memoryUsage: 0
  },
  setTelemetryData: (data) => set((state) => ({
    telemetryData: { ...state.telemetryData, ...data }
  })),
  
  backendConnected: false,
  setBackendConnected: (connected) => set({ backendConnected: connected }),
  
  checkBackendHealth: async () => {
    try {
      const response = await fetch(`${API_BASE}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      
      if (response.ok) {
        const data = await response.json();
        set({ 
          backendConnected: true,
          systemVRAM: data.vram_usage_gb ? Math.round(data.vram_usage_gb * 1024) : get().systemVRAM
        });
      } else {
        set({ backendConnected: false });
      }
    } catch {
      set({ backendConnected: false });
    }
  },
  
  // ------------------------------------------------------------------
  // UI STATE & SESSION
  // ------------------------------------------------------------------
  isSidebarOpen: true,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  
  session_id: '',
  generateSessionId: async () => {
    try {
      const sessionId = await invoke<string>('generate_new_session');
      set({ session_id: sessionId });
    } catch {
      set({ session_id: `session-${Date.now()}` });
    }
  },
  
  // ------------------------------------------------------------------
  // SESSIONS MANAGEMENT
  // ------------------------------------------------------------------
  sessions: [],
  setSessions: (sessions) => set({ sessions }),
  addSession: (session) => set((state) => ({
    sessions: [session, ...state.sessions]
  })),
  removeSession: (sessionId) => set((state) => ({
    sessions: state.sessions.filter(s => s.id !== sessionId)
  }))
}));