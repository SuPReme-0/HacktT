import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/tauri';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import { createClient } from '@supabase/supabase-js';

// ======================================================================
// 1. SUPABASE CLIENT INITIALIZATION
// ======================================================================
const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co',
  import.meta.env.VITE_SUPABASE_ANON_KEY || 'your-anon-key'
);

// ======================================================================
// 2. TYPE DEFINITIONS
// ======================================================================
export interface User {
  name: string;
  email: string;
  avatarUrl: string;
  token?: string;
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

// ======================================================================
// 3. SYSTEM STATE INTERFACE
// ======================================================================
interface SystemState {
  // Auth & Identity
  user: User | null;
  setUser: (user: User | null) => void;
  loginWithGoogle: () => Promise<void>;
  sendEmailOtp: (email: string) => Promise<void>;
  verifyEmailOtp: (email: string, otp: string) => Promise<User>;
  updateOperatorProfile: (name: string) => Promise<void>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
  
  // Hardware & Network
  systemVRAM: number;
  setSystemVRAM: (vram: number) => void;
  idePort: number;
  browserPort: number;
  initSystem: () => Promise<void>;
  
  // Operational Modes
  mode: 'active' | 'passive';
  isProcessing: boolean;
  isSpeaking: boolean;
  threatLevel: 'safe' | 'medium' | 'high';
  vaultSkills: VaultSkill[];
  toggleMode: () => Promise<void>;
  
  // Permissions Matrix
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
  
  // UI State
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  
  // Session Management
  session_id: string;
  generateSessionId: () => void;
}

// ======================================================================
// 4. ZUSTAND STORE IMPLEMENTATION
// ======================================================================
export const useSystemStore = create<SystemState>((set, get) => ({
  // ==================================================================
  // AUTH & IDENTITY
  // ==================================================================
  user: null,
  setUser: (user) => set({ user }),
  
  loginWithGoogle: async () => {
    try {
      await invoke('trigger_google_auth');
    } catch (error: any) {
      console.error('Google Auth failed:', error.message);
      throw error;
    }
  },
  
  sendEmailOtp: async (email: string) => {
    try {
      const { error } = await supabase.auth.signInWithOtp({ 
        email,
        options: {
          emailRedirectTo: 'hackt://auth-callback'
        }
      });
      if (error) throw error;
    } catch (error: any) {
      console.error('OTP Send failed:', error.message);
      throw error;
    }
  },
  
  verifyEmailOtp: async (email: string, otp: string) => {
    try {
      const { data, error } = await supabase.auth.verifyOtp({
        email,
        token: otp,
        type: 'email'
      });
      if (error) throw error;
      
      return {
        name: data.user?.user_metadata?.name || 'Operator',
        email: data.user?.email || '',
        avatarUrl: data.user?.user_metadata?.avatar_url || 
                   `https://ui-avatars.com/api/?name=${encodeURIComponent(data.user?.email || 'Operator')}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`,
        token: data.session?.access_token || ''
      };
    } catch (error: any) {
      console.error('OTP Verify failed:', error.message);
      throw error;
    }
  },
  
  updateOperatorProfile: async (name: string) => {
    try {
      const { error } = await supabase.auth.updateUser({
        data: { name }
      });
      if (error) throw error;
    } catch (error: any) {
      console.error('Profile Update failed:', error.message);
      throw error;
    }
  },
  
  checkSession: async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        set({
          user: {
            name: session.user.user_metadata?.name || 'Operator',
            email: session.user.email || '',
            avatarUrl: session.user.user_metadata?.avatar_url || 
                       `https://ui-avatars.com/api/?name=${encodeURIComponent(session.user.email || 'Operator')}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`,
            token: session.access_token
          }
        });
      }
    } catch (error: any) {
      console.warn('Session check failed:', error.message);
    }
  },
  
  logout: async () => {
    try {
      await supabase.auth.signOut();
    } catch (error: any) {
      console.error('Logout failed:', error.message);
    } finally {
      set({ user: null, messages: [], activeContext: {} });
    }
  },
  
  // ==================================================================
  // HARDWARE & NETWORK
  // ==================================================================
  systemVRAM: 0,
  setSystemVRAM: (vram) => set({ systemVRAM: vram }),
  idePort: 8081,
  browserPort: 8082,
  
  initSystem: async () => {
    let unlistenOAuth: UnlistenFn | undefined;
    let unlistenThreat: UnlistenFn | undefined;
    let unlistenContext: UnlistenFn | undefined;
    let unlistenTelemetry: UnlistenFn | undefined;
    
    try {
      // 1. Fetch VRAM from Rust backend
      const vram = await invoke<number>('get_system_vram');
      set({ systemVRAM: vram });
      
      // 2. Generate session ID
      const sessionId = await invoke<string>('generate_new_session');
      set({ session_id: sessionId });
      
      // 3. OAuth Callback Listener
      unlistenOAuth = await listen('oauth_callback', (event) => {
        const payload = event.payload as { name: string; email: string; avatar: string; token: string };
        set({
          user: {
            name: payload.name || 'Operator',
            email: payload.email || '',
            avatarUrl: payload.avatar || 
                       `https://ui-avatars.com/api/?name=${encodeURIComponent(payload.name || 'Operator')}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`,
            token: payload.token || ''
          }
        });
      });
      
      // 4. Threat Alert Listener
      unlistenThreat = await listen('threat_detected', (event) => {
        const payload = event.payload as { level: string; source?: string };
        set({ 
          threatLevel: (payload.level as 'safe' | 'medium' | 'high') || 'safe',
          telemetryData: {
            ...get().telemetryData,
            threatsDetected: get().telemetryData.threatsDetected + 1,
            lastScanTime: new Date().toLocaleTimeString()
          }
        });
      });
      
      // 5. IDE Context Listener (Real-time file updates)
      unlistenContext = await listen('ide_context_update', (event) => {
        const payload = event.payload as ActiveContext;
        set({ activeContext: payload });
      });
      
      // 6. Telemetry Updates Listener
      unlistenTelemetry = await listen('telemetry_update', (event) => {
        const payload = event.payload as Partial<TelemetryData>;
        set((state) => ({
          telemetryData: {
            ...state.telemetryData,
            ...payload,
            lastScanTime: new Date().toLocaleTimeString()
          }
        }));
      });
      
      // 7. Check Backend Health
      await get().checkBackendHealth();
      
      // 8. Start health check interval
      setInterval(() => get().checkBackendHealth(), 5000);
      
    } catch (error: any) {
      console.warn('System initialization failed:', error.message);
      set({ systemVRAM: 8192 });
    }
    
    // Cleanup function for listeners
    return () => {
      unlistenOAuth?.();
      unlistenThreat?.();
      unlistenContext?.();
      unlistenTelemetry?.();
    };
  },
  
  // ==================================================================
  // OPERATIONAL MODES
  // ==================================================================
  mode: 'active',
  isProcessing: false,
  isSpeaking: false,
  threatLevel: 'safe',
  vaultSkills: [
    { chapter: 'Network Forensics', topicsCovered: ['Wireshark', 'Packet Sniffing'] },
    { chapter: 'Web Exploitation', topicsCovered: ['XSS', 'SQLi', 'CSRF'] },
    { chapter: 'Binary Analysis', topicsCovered: ['Reverse Engineering', 'Malware Analysis'] },
    { chapter: 'Cloud Security', topicsCovered: ['AWS Security', 'Azure Security'] }
  ],
  
  toggleMode: async () => {
    const { mode, systemVRAM } = get();
    
    // VRAM Safety Lock for Passive Mode
    if (mode === 'active' && systemVRAM < 6144) {
      console.warn('Insufficient VRAM for Passive Mode (6GB required)');
      throw new Error('Insufficient VRAM for Passive Mode');
    }
    
    const newMode = mode === 'active' ? 'passive' : 'active';
    
    try {
      await invoke('set_monitoring_mode', { mode: newMode });
      set({ mode: newMode });
      
      // Show bubble window when entering passive mode
      if (newMode === 'passive') {
        await invoke('show_bubble_window');
      } else {
        await invoke('hide_bubble_window');
      }
    } catch (error: any) {
      console.error('Mode toggle failed:', error.message);
      throw error;
    }
  },
  
  // ==================================================================
  // PERMISSIONS MATRIX
  // ==================================================================
  permissions: {
    micEnabled: false,
    visionEnabled: false,
    ideIntegration: false,
    browserIntegration: false,
    cloudSync: false,
  },
  
  togglePermission: async (key: keyof Permissions) => {
    const { permissions, idePort, browserPort } = get();
    const isNowEnabled = !permissions[key];
    
    // VRAM Check for Vision
    if (key === 'visionEnabled' && isNowEnabled) {
      const { systemVRAM } = get();
      if (systemVRAM < 6144) {
        throw new Error('Insufficient VRAM for Vision (6GB required)');
      }
    }
    
    try {
      if (key === 'ideIntegration') {
        await invoke('toggle_port_listener', { 
          port: idePort, 
          service: 'ide', 
          state: isNowEnabled 
        });
      } else if (key === 'browserIntegration') {
        await invoke('toggle_port_listener', { 
          port: browserPort, 
          service: 'browser', 
          state: isNowEnabled 
        });
      } else if (key === 'visionEnabled') {
        const action = isNowEnabled ? 'start_vision' : 'stop_vision';
        await invoke(action);
      } else if (key === 'micEnabled') {
        const action = isNowEnabled ? 'start_mic' : 'stop_mic';
        await invoke(action);
      } else if (key === 'cloudSync') {
        if (isNowEnabled) {
          await invoke('sync_vault_to_cloud');
        }
      }
      
      set((state) => ({
        permissions: { ...state.permissions, [key]: isNowEnabled }
      }));
    } catch (error: any) {
      console.error(`Permission toggle failed for ${key}:`, error.message);
      throw error;
    }
  },
  
  // ==================================================================
  // CHAT INTERFACE
  // ==================================================================
  messages: [
    { 
      id: 'init', 
      sender: 'system', 
      text: 'Sovereign Vault online. Awaiting commands.', 
      timestamp: new Date() 
    }
  ],
  
  sendMessage: async (text: string) => {
    const { mode, session_id } = get();
    
    // Add user message immediately for UI responsiveness
    set((state) => ({
      messages: [
        ...state.messages, 
        { 
          id: Date.now().toString(), 
          sender: 'user', 
          text, 
          timestamp: new Date() 
        }
      ],
      isProcessing: true
    }));
    
    try {
      // Stream response from Python backend
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          prompt: text, 
          mode, 
          session_id 
        })
      });
      
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let aiText = '';
      
      // Add placeholder for streaming message
      set((state) => ({
        messages: [
          ...state.messages, 
          {
            id: 'streaming',
            sender: 'ai',
            text: '',
            timestamp: new Date()
          }
        ]
      }));
      
      // Read stream chunks
      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;
        aiText += decoder.decode(value);
        
        // Update streaming message in real-time
        set((state) => ({
          messages: state.messages.map(m => 
            m.id === 'streaming' ? { ...m, text: aiText } : m
          )
        }));
      }
      
      // Finalize message with unique ID
      set((state) => ({
        messages: state.messages.map(m => 
          m.id === 'streaming' ? { ...m, id: (Date.now() + 1).toString() } : m
        ),
        isProcessing: false
      }));
      
    } catch (error: any) {
      console.error('Chat send failed:', error.message);
      set((state) => ({
        messages: [
          ...state.messages, 
          {
            id: (Date.now() + 1).toString(),
            sender: 'system',
            text: `[ERROR]: Failed to connect to local AI Core. ${error.message}`,
            timestamp: new Date()
          }
        ],
        isProcessing: false
      }));
    }
  },
  
  // ==================================================================
  // IDE CONTEXT & TELEMETRY
  // ==================================================================
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
  
  // ==================================================================
  // BACKEND CONNECTION
  // ==================================================================
  backendConnected: false,
  setBackendConnected: (connected) => set({ backendConnected: connected }),
  
  checkBackendHealth: async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/health', {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      set({ backendConnected: response.ok });
    } catch {
      set({ backendConnected: false });
    }
  },
  
  // ==================================================================
  // UI STATE
  // ==================================================================
  isSidebarOpen: true,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  
  // ==================================================================
  // SESSION MANAGEMENT
  // ==================================================================
  session_id: '',
  generateSessionId: async () => {
    try {
      const sessionId = await invoke<string>('generate_new_session');
      set({ session_id: sessionId });
    } catch (error: any) {
      console.warn('Session ID generation failed:', error.message);
      set({ session_id: `session-${Date.now()}` });
    }
  }
}));