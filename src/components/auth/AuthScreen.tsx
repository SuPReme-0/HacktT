import React, { useState, useEffect } from 'react';
import { useSystemStore } from '../../store/systemStore';
import { 
  Mail, ShieldAlert, UserPlus, Key, 
  CheckCircle, AlertTriangle, Loader2, ArrowLeft,
  Chrome
} from 'lucide-react';

export default function AuthScreen() {
  const { 
    loginWithGoogle, 
    setUser,
    sendEmailOtp,
    verifyEmailOtp,
    updateOperatorProfile,
    checkSession
  } = useSystemStore();
  
  // Auth States
  const [authStep, setAuthStep] = useState<'initial' | 'email' | 'otp' | 'setup'>('initial');
  
  // Form States
  const [emailAuth, setEmailAuth] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [operatorName, setOperatorName] = useState('');
  
  // UI States
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  // ======================================================================
  // 1. SESSION CHECK & OAUTH LISTENER
  // ======================================================================
  useEffect(() => {
    checkSession();

    // ✅ MOCK-SAFE: Only listen if Tauri is available
    let unlisten: (() => void) | undefined;
    
    const setupOAuthListener = async () => {
      try {
        // Dynamic import to avoid errors in web testing
        const { listen } = await import('@tauri-apps/api/event');
        
        unlisten = await listen('oauth_callback', (event) => {
          const payload = event.payload as { 
            name: string; 
            email: string; 
            avatar: string; 
            token: string 
          };
          
          if (payload.email) {
            setUser({
              name: payload.name || 'Operator',
              email: payload.email,
              avatarUrl: payload.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(payload.name || 'Operator')}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`,
              token: payload.token
            });
            setSuccess('Google authentication successful. Welcome aboard.');
          }
        });
      } catch {
        // Tauri not available (web testing mode) - silently fail
        console.warn('OAuth listener not available (web mode)');
      }
    };

    setupOAuthListener();

    return () => {
      unlisten?.();
    };
  }, [checkSession, setUser]);

  // ======================================================================
  // 2. COUNTDOWN TIMER FOR OTP RESEND
  // ======================================================================
  useEffect(() => {
    if (countdown > 0) {
      const timer = setInterval(() => setCountdown(c => c - 1), 1000);
      return () => clearInterval(timer);
    }
  }, [countdown]);

  // ======================================================================
  // 3. CLEAR ERROR/SUCCESS AFTER DELAY
  // ======================================================================
  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccess(null);
      }, error ? 5000 : 8000); // ✅ Longer for success messages
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  // ======================================================================
  // 4. AUTH HANDLERS
  // ======================================================================
  const handleGoogleAuth = async () => {
    setAuthLoading(true);
    setError(null);
    try {
      await loginWithGoogle();
    } catch (err: any) {
      setError(err.message || 'Google authentication failed');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setError(null);
    try {
      await sendEmailOtp(emailAuth);
      setAuthStep('otp');
      setCountdown(30);
      setSuccess('Access code transmitted to your email.');
    } catch (err: any) {
      setError(err.message || 'Failed to send access code');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setError(null);
    try {
      const verifiedUser = await verifyEmailOtp(emailAuth, otpCode);
      
      if (!verifiedUser?.name || verifiedUser.name.trim() === '') {
        setAuthStep('setup');
      } else {
        setUser({
          name: verifiedUser.name,
          email: verifiedUser.email,
          avatarUrl: verifiedUser.avatarUrl || `https://ui-avatars.com/api/?name=${encodeURIComponent(verifiedUser.name)}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`,
          token: verifiedUser.token
        });
        setSuccess('Identity verified. Access granted.');
      }
    } catch (err: any) {
      setError(err.message || 'Invalid access code');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleFinalizeSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setError(null);
    try {
      await updateOperatorProfile(operatorName);
      
      setUser({
        name: operatorName,
        email: emailAuth,
        avatarUrl: `https://ui-avatars.com/api/?name=${encodeURIComponent(operatorName)}&background=0a0a0a&color=00f3ff&rounded=true&bold=true`
      });
      setSuccess('Operator profile initialized. Welcome to HackT.');
    } catch (err: any) {
      setError(err.message || 'Profile setup failed');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (countdown > 0) return;
    try {
      await sendEmailOtp(emailAuth);
      setCountdown(30);
      setSuccess('New access code sent.');
    } catch (err: any) {
      setError(err.message || 'Failed to resend code');
    }
  };

  // ======================================================================
  // 5. EXTRACTED RENDER HELPERS (Cleaner Code)
  // ======================================================================
  const renderToast = () => {
    if (!error && !success) return null;
    
    return (
      <div className={`mb-4 p-3 rounded-lg border flex items-center gap-2 text-xs animate-in slide-in-from-top-2 ${
        error 
          ? 'bg-red-900/20 border-red-500/30 text-red-400' 
          : 'bg-green-900/20 border-green-500/30 text-green-400'
      }`}>
        {error ? <AlertTriangle size={14} /> : <CheckCircle size={14} />}
        <span>{error || success}</span>
      </div>
    );
  };

  const renderInitialStep = () => (
    <div className="space-y-4 animate-in fade-in duration-300">
      <button 
        onClick={handleGoogleAuth}
        disabled={authLoading}
        className="w-full flex items-center justify-center gap-3 py-4 border border-[#00f3ff]/50 text-[#00f3ff] rounded-xl bg-[#00f3ff]/5 hover:bg-[#00f3ff]/15 hover:shadow-[0_0_25px_rgba(0,243,255,0.3)] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group"
      >
        {authLoading ? (
          <Loader2 size={18} className="animate-spin" />
        ) : (
          <Chrome size={18} className="group-hover:scale-110 transition-transform" />
        )}
        <span className="font-bold text-sm tracking-widest">CONNECT GOOGLE SSO</span>
      </button>
      
      <div className="relative flex items-center py-3">
        <div className="flex-grow border-t border-[#1f1f1f]"></div>
        <span className="flex-shrink-0 mx-4 text-[9px] text-gray-600 tracking-widest">OR SECURE EMAIL</span>
        <div className="flex-grow border-t border-[#1f1f1f]"></div>
      </div>

      <button 
        onClick={() => setAuthStep('email')}
        disabled={authLoading}
        className="w-full flex items-center justify-center gap-3 py-4 border border-[#1f1f1f] text-gray-400 rounded-xl hover:bg-[#1f1f1f] hover:text-white hover:border-[#00f3ff]/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group"
      >
        <Mail size={18} className="group-hover:scale-110 transition-transform" />
        <span className="font-bold text-sm tracking-widest">EMAIL ACCESS CODE</span>
      </button>

      <div className="pt-4 text-center">
        <p className="text-[9px] text-gray-600 uppercase tracking-widest">
          By continuing, you agree to our{' '}
          <span className="text-[#00f3ff] cursor-pointer hover:underline">Terms</span>
          {' '}and{' '}
          <span className="text-[#00f3ff] cursor-pointer hover:underline">Privacy Policy</span>
        </p>
      </div>
    </div>
  );

  const renderEmailStep = () => (
    <form onSubmit={handleSendOtp} className="space-y-5 animate-in fade-in slide-in-from-right-8 duration-300">
      <div>
        <label className="block text-[9px] text-gray-500 uppercase tracking-widest mb-2">Operator Email</label>
        <div className="relative">
          <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-600" size={18} />
          <input 
            type="email" 
            required
            value={emailAuth}
            onChange={(e) => setEmailAuth(e.target.value)}
            placeholder="operator@hackt.local" 
            className="w-full input-3d rounded-xl py-4 pl-12 pr-4 text-white text-sm font-mono focus:outline-none placeholder-gray-600 tracking-widest"
          />
        </div>
      </div>
      
      <button 
        type="submit" 
        disabled={authLoading || !emailAuth}
        className="w-full py-4 bg-[#1f1f1f] text-gray-300 rounded-xl hover:text-[#00f3ff] hover:bg-black hover:border-[#00f3ff]/30 transition-all border border-transparent hover:shadow-[0_0_20px_rgba(0,243,255,0.2)] text-sm tracking-widest font-bold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {authLoading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            TRANSMITTING...
          </>
        ) : (
          <>
            <Key size={16} />
            REQUEST ACCESS CODE
          </>
        )}
      </button>
      
      <button 
        type="button" 
        onClick={() => setAuthStep('initial')} 
        className="w-full text-[9px] text-gray-500 hover:text-white tracking-widest mt-2 flex items-center justify-center gap-1 group"
      >
        <ArrowLeft size={12} className="group-hover:-translate-x-1 transition-transform" />
        BACK TO AUTH SELECTION
      </button>
    </form>
  );

  const renderOtpStep = () => (
    <form onSubmit={handleVerifyOtp} className="space-y-5 animate-in fade-in slide-in-from-right-8 duration-300">
      <div className="text-center">
        <p className="text-[9px] text-gray-400 uppercase tracking-widest mb-2">Access Code Sent To:</p>
        <p className="text-sm text-[#00f3ff] font-mono">{emailAuth}</p>
      </div>
      
      <div>
        <label className="block text-[9px] text-gray-500 uppercase tracking-widest mb-2 text-center">6-Digit Code</label>
        <input 
          type="text" 
          required
          maxLength={6}
          value={otpCode}
          onChange={(e) => setOtpCode(e.target.value.replace(/[^0-9]/g, ''))}
          placeholder="0 0 0 0 0 0" 
          className="w-full input-3d rounded-xl py-5 px-4 text-[#00f3ff] text-4xl font-mono focus:outline-none placeholder-gray-700 text-center tracking-[0.8em] font-bold"
          autoFocus
        />
      </div>
      
      <button 
        type="submit" 
        disabled={authLoading || otpCode.length !== 6}
        className="w-full py-4 bg-[#00f3ff]/10 text-[#00f3ff] rounded-xl hover:bg-[#00f3ff]/20 transition-all border border-[#00f3ff]/30 hover:shadow-[0_0_25px_rgba(0,243,255,0.3)] text-sm tracking-widest font-bold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {authLoading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            DECRYPTING...
          </>
        ) : (
          <>
            <ShieldAlert size={16} />
            VERIFY IDENTITY
          </>
        )}
      </button>

      <div className="text-center">
        <button 
          type="button"
          onClick={handleResendOtp}
          disabled={countdown > 0}
          className="text-[9px] text-gray-500 hover:text-[#00f3ff] tracking-widest disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {countdown > 0 
            ? `RESEND CODE IN ${countdown}s` 
            : 'RESEND ACCESS CODE'}
        </button>
      </div>
      
      <button 
        type="button" 
        onClick={() => setAuthStep('email')} 
        className="w-full text-[9px] text-gray-500 hover:text-white tracking-widest mt-2 flex items-center justify-center gap-1 group"
      >
        <ArrowLeft size={12} className="group-hover:-translate-x-1 transition-transform" />
        CHANGE EMAIL
      </button>
    </form>
  );

  const renderSetupStep = () => (
    <form onSubmit={handleFinalizeSetup} className="space-y-5 animate-in fade-in slide-in-from-right-8 duration-300">
      <div className="p-4 rounded-xl bg-[#00f3ff]/5 border border-[#00f3ff]/20">
        <p className="text-[9px] text-gray-400 uppercase tracking-widest text-center">
          First time detected. Establish your operator identity for the Knowledge Vault.
        </p>
      </div>
      
      <div>
        <label className="block text-[9px] text-[#00f3ff] uppercase tracking-widest mb-2">Operator Alias</label>
        <div className="relative">
          <UserPlus className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-600" size={18} />
          <input 
            type="text" 
            required
            minLength={2}
            value={operatorName}
            onChange={(e) => setOperatorName(e.target.value)}
            placeholder="Enter your alias..." 
            className="w-full input-3d rounded-xl py-4 pl-12 pr-4 text-white text-sm font-mono focus:outline-none placeholder-gray-600 tracking-widest border border-[#00f3ff]/30 focus:border-[#00f3ff]"
            autoFocus
          />
          <p className="text-[8px] text-gray-600 mt-2 text-center">
            This name will be used for all vault operations and session logs.
          </p>
        </div>
      </div>
      
      <button 
        type="submit" 
        disabled={authLoading || operatorName.length < 2}
        className="w-full py-4 bg-[#00f3ff]/10 text-[#00f3ff] rounded-xl hover:bg-[#00f3ff]/20 transition-all border border-[#00f3ff]/30 hover:shadow-[0_0_25px_rgba(0,243,255,0.3)] text-sm tracking-widest font-bold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {authLoading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            INITIALIZING...
          </>
        ) : (
          <>
            <CheckCircle size={16} />
            FINALIZE REGISTRATION
          </>
        )}
      </button>
    </form>
  );

  // ======================================================================
  // 6. MAIN RENDER
  // ======================================================================
  return (
    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[#030305]/95 backdrop-blur-xl text-[#e0e0e0] font-mono selection:bg-[#00f3ff] selection:text-black">
      
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#00f3ff]/5 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#bc13fe]/5 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }} />
      </div>

      {/* Top Left Branding */}
      <div className="absolute top-8 left-8 z-10">
        <h1 className="text-2xl font-bold tracking-widest text-white drop-shadow-[0_0_10px_rgba(0,243,255,0.5)]">
          HACKT<span className="text-[#00f3ff]">.AI</span>
        </h1>
        <div className="text-[10px] text-red-500 uppercase tracking-widest flex items-center gap-2 mt-1">
          <div className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
          System Locked
        </div>
      </div>

      {/* Top Right - Session Status */}
      <div className="absolute top-8 right-8 z-10">
        <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase tracking-widest">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          Secure Connection
        </div>
      </div>

      {/* 3D Auth Module */}
      <div className="w-full max-w-md panel-3d rounded-2xl p-8 transform transition-all duration-500 shadow-[0_0_80px_rgba(0,0,0,0.5)] border border-[#1f1f1f] relative z-10">
        
        {/* Dynamic Header */}
        <div className="text-center mb-8">
          {authStep === 'setup' ? (
            <div className="relative inline-block">
              <UserPlus className="mx-auto mb-4 text-[#00f3ff] drop-shadow-[0_0_20px_rgba(0,243,255,0.5)]" size={56} />
              <div className="absolute inset-0 bg-[#00f3ff]/20 blur-xl rounded-full" />
            </div>
          ) : (
            <div className="relative inline-block">
              <ShieldAlert className="mx-auto mb-4 text-[#bc13fe] drop-shadow-[0_0_20px_rgba(188,19,254,0.5)]" size={56} />
              <div className="absolute inset-0 bg-[#bc13fe]/20 blur-xl rounded-full" />
            </div>
          )}
          
          <h2 className="text-2xl font-bold tracking-widest text-white mb-2">
            {authStep === 'setup' ? 'NEW OPERATOR' : 
             authStep === 'initial' ? 'AUTH REQUIRED' :
             authStep === 'email' ? 'ENTER EMAIL' :
             authStep === 'otp' ? 'VERIFY IDENTITY' : 'LOGIN'}
          </h2>
          <p className="text-xs text-gray-400 uppercase tracking-widest">
            {authStep === 'setup' ? 'Initialize Identity Alias' : 
             authStep === 'initial' ? 'Decrypt Local Knowledge Vault' :
             authStep === 'email' ? 'Receive Secure Access Code' :
             authStep === 'otp' ? 'Enter 6-Digit Code' : 'Access Your Account'}
          </p>
        </div>

        {/* Toast Notifications */}
        {renderToast()}

        {/* Step Rendering */}
        {authStep === 'initial' && renderInitialStep()}
        {authStep === 'email' && renderEmailStep()}
        {authStep === 'otp' && renderOtpStep()}
        {authStep === 'setup' && renderSetupStep()}
      </div>

      {/* Footer */}
      <div className="absolute bottom-8 text-[9px] text-gray-600 uppercase tracking-widest text-center z-10 space-y-1">
        <div className="flex items-center justify-center gap-4">
          <span className="flex items-center gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
            Local Execution
          </span>
          <span className="flex items-center gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-[#00f3ff]" />
            End-to-End Encryption
          </span>
          <span className="flex items-center gap-1">
            <div className="h-1.5 w-1.5 rounded-full bg-[#bc13fe]" />
            Sovereign Vault
          </span>
        </div>
        <span className="opacity-50">HackT Runtime v1.0.0 • Build 2024.12</span>
      </div>

      {/* Security Badge */}
      <div className="absolute bottom-8 right-8 z-10">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#0a0a0a]/80 border border-[#1f1f1f]">
          <ShieldAlert size={12} className="text-[#bc13fe]" />
          <span className="text-[8px] text-gray-500 uppercase tracking-widest">AES-256 Encrypted</span>
        </div>
      </div>
    </div>
  );
}