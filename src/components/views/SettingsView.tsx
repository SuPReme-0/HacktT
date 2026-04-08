import { useState, useRef, useEffect, memo } from 'react';
import { useSystemStore } from '../../store/systemStore';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  Send, Terminal, Cpu, Zap, Mic, Volume2, VolumeX,
  Code, Activity, Sparkles, History, Lightbulb,
  RefreshCw, AlertCircle, Copy, ThumbsUp, ThumbsDown,
  CheckCircle, X, Keyboard
} from 'lucide-react';

// ======================================================================
// TYPE DEFINITIONS
// ======================================================================
interface Suggestion {
  id: string;
  type: 'ide' | 'history' | 'context' | 'quick';
  text: string;
  icon: React.ReactNode;
  priority: number;
}

interface MessageItemProps {
  msg: {
    id: string;
    sender: 'user' | 'ai' | 'system';
    text: string;
    timestamp: Date;
  };
  isPassive: boolean;
  copiedMessageId: string | null;
  onCopy: (text: string, id: string) => void;
  onFeedback: (id: string, feedback: 'up' | 'down') => void;
}

// ======================================================================
// OPTIMIZED MESSAGE COMPONENT (Prevents Re-renders)
// ======================================================================
const MessageItem = memo(({ msg, isPassive, copiedMessageId, onCopy, onFeedback }: MessageItemProps) => {
  return (
    <div className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-forwards`}>
      <div className={`max-w-[85%] rounded-xl p-5 text-sm panel-3d shadow-xl transition-all duration-300 hover:shadow-2xl group ${
        msg.sender === 'user'
          ? 'bg-[#1a1a1a]/90 text-gray-200 border-[#333]'
          : `bg-[#050505]/95 ${isPassive ? 'border-[#bc13fe]/40 text-[#e0e0e0]' : 'border-[#00f3ff]/40 text-[#e0e0e0]'}`
      }`}>
        
        {/* AI Header Badge */}
        {msg.sender === 'ai' && (
          <div className={`text-[10px] mb-3 uppercase tracking-widest font-bold flex items-center gap-2 ${
            isPassive ? 'text-[#bc13fe]' : 'text-[#00f3ff]'
          }`}>
            <div className={`h-1.5 w-1.5 rounded-full ${
              isPassive
                ? 'bg-[#bc13fe] shadow-[0_0_5px_#bc13fe]'
                : 'bg-[#00f3ff] shadow-[0_0_5px_#00f3ff]'
            } animate-pulse`} />
            HackT Core
            <span className="text-gray-600 font-normal ml-2">
              {new Date(msg.timestamp).toLocaleTimeString()}
            </span>
          </div>
        )}
        
        {/* Message Content with Markdown & Code Highlighting */}
        <div className="font-mono leading-relaxed whitespace-pre-wrap">
          {msg.sender === 'ai' ? (
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <div className="relative group/code my-3 rounded-lg overflow-hidden border border-white/10">
                      <div className="flex justify-between items-center bg-black/40 px-4 py-1 border-b border-white/5">
                        <span className="text-[10px] text-gray-500 font-mono">{match[1]}</span>
                      </div>
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{ margin: 0, padding: '1rem', background: 'transparent' }}
                        {...props}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                      <button
                        onClick={() => onCopy(String(children), msg.id)}
                        className="absolute top-2 right-2 p-1.5 rounded bg-black/50 opacity-0 group-hover/code:opacity-100 transition-opacity hover:bg-white/20"
                      >
                        {copiedMessageId === msg.id ? (
                          <CheckCircle size={14} className="text-green-400" />
                        ) : (
                          <Copy size={14} className="text-white" />
                        )}
                      </button>
                    </div>
                  ) : (
                    <code className="bg-white/5 px-1.5 py-0.5 rounded text-[#00f3ff]" {...props}>
                      {children}
                    </code>
                  );
                }
              }}
            >
              {msg.text}
            </ReactMarkdown>
          ) : (
            <span>{msg.text}</span>
          )}
        </div>

        {/* Message Actions (AI only) */}
        {msg.sender === 'ai' && (
          <div className="flex items-center gap-2 mt-4 pt-3 border-t border-white/5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onCopy(msg.text, msg.id)}
              className="p-1.5 rounded hover:bg-white/5 text-gray-500 hover:text-white transition-colors"
              title="Copy response"
            >
              {copiedMessageId === msg.id ? (
                <CheckCircle size={12} className="text-green-400" />
              ) : (
                <Copy size={12} />
              )}
            </button>
            <button
              onClick={() => onFeedback(msg.id, 'up')}
              className="p-1.5 rounded hover:bg-white/5 text-gray-500 hover:text-green-400 transition-colors"
              title="Helpful"
            >
              <ThumbsUp size={12} />
            </button>
            <button
              onClick={() => onFeedback(msg.id, 'down')}
              className="p-1.5 rounded hover:bg-white/5 text-gray-500 hover:text-red-400 transition-colors"
              title="Not helpful"
            >
              <ThumbsDown size={12} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}, (prev, next) => {
  // Only re-render if text or mode actually changed (critical for streaming)
  return prev.msg.text === next.msg.text && prev.isPassive === next.isPassive;
});

// ======================================================================
// MAIN COMPONENT
// ======================================================================
export default function ChatView() {
  const {
    messages,
    sendMessage,
    mode,
    isProcessing,
    permissions,
    vaultSkills,
    activeContext,
    backendConnected,
  } = useSystemStore();

  // Local States
  const [input, setInput] = useState('');
  const [isThundering, setIsThundering] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [charCount, setCharCount] = useState(0);
  const MAX_CHARS = 1000;

  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // ======================================================================
  // 1. AUTO-SCROLL TO LATEST MESSAGE (Optimized for Streaming)
  // ======================================================================
  useEffect(() => {
    if (endOfMessagesRef.current) {
      endOfMessagesRef.current.scrollIntoView({ 
        behavior: isProcessing ? 'auto' : 'smooth', // 'auto' is 10x faster for streams
        block: 'end' 
      });
    }
  }, [messages, isProcessing]);

  // ======================================================================
  // 2. UPDATE CHAR COUNT
  // ======================================================================
  useEffect(() => {
    setCharCount(input.length);
  }, [input]);

  // ======================================================================
  // 3. GENERATE SMART SUGGESTIONS (Deduplicated)
  // ======================================================================
  useEffect(() => {
    const generateSuggestions = () => {
      const newSuggestions: Suggestion[] = [];
      const existingTexts = new Set(messages.map(m => m.text.toLowerCase()));

      // IDE Context Suggestions (Passive Mode)
      if (mode === 'passive' && permissions.ideIntegration && activeContext.file) {
        const ideSuggestion1 = `Analyze ${activeContext.file} for vulnerabilities`;
        if (!existingTexts.has(ideSuggestion1.toLowerCase())) {
          newSuggestions.push({
            id: 'ide-1',
            type: 'ide',
            text: ideSuggestion1,
            icon: <Code size={12} />,
            priority: 1
          });
        }
        const ideSuggestion2 = 'Optimize current file performance';
        if (!existingTexts.has(ideSuggestion2.toLowerCase())) {
          newSuggestions.push({
            id: 'ide-2',
            type: 'ide',
            text: ideSuggestion2,
            icon: <Zap size={12} />,
            priority: 2
          });
        }
      }

      // Recent History Suggestions
      const userMessages = messages.filter(m => m.sender === 'user');
      if (userMessages.length > 0) {
        const lastUserMessage = userMessages.slice(-1)[0];
        if (lastUserMessage) {
          const historySuggestion = `Continue: ${lastUserMessage.text.slice(0, 40)}...`;
          if (!existingTexts.has(historySuggestion.toLowerCase())) {
            newSuggestions.push({
              id: 'hist-1',
              type: 'history',
              text: historySuggestion,
              icon: <History size={12} />,
              priority: 3
            });
          }
        }
      }

      // Context-Aware Suggestions (Vault Skills)
      if (vaultSkills.length > 0) {
        const randomSkill = vaultSkills[Math.floor(Math.random() * vaultSkills.length)];
        const contextSuggestion = `Explain ${randomSkill.chapter} concepts`;
        if (!existingTexts.has(contextSuggestion.toLowerCase())) {
          newSuggestions.push({
            id: 'ctx-1',
            type: 'context',
            text: contextSuggestion,
            icon: <Lightbulb size={12} />,
            priority: 4
          });
        }
      }

      // Quick Action Suggestions
      const quickSuggestions = [
        { id: 'quick-1', text: 'Scan current screen for threats', icon: <Activity size={12} />, priority: 5 },
        { id: 'quick-2', text: 'Show security best practices', icon: <Sparkles size={12} />, priority: 6 }
      ];
      
      quickSuggestions.forEach(qs => {
        if (!existingTexts.has(qs.text.toLowerCase())) {
          newSuggestions.push({
            id: qs.id,
            type: 'quick',
            text: qs.text,
            icon: qs.icon,
            priority: qs.priority
          });
        }
      });

      setSuggestions(newSuggestions.sort((a, b) => a.priority - b.priority).slice(0, 4));
    };

    if (!isProcessing && showSuggestions) {
      generateSuggestions();
    }
  }, [mode, permissions.ideIntegration, activeContext, messages, vaultSkills, isProcessing, showSuggestions]);

  // ======================================================================
  // 4. KEYBOARD SHORTCUTS & FOCUS TRAP
  // ======================================================================
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K to focus input
      if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
      // Ctrl+Enter to send
      if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        if (input.trim() && !isProcessing) {
          handleSend();
        }
      }
      // Escape to clear input
      if (e.key === 'Escape' && document.activeElement === inputRef.current) {
        setInput('');
        setShowSuggestions(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [input, isProcessing]);

  // Focus input when AI finishes processing
  useEffect(() => {
    if (!isProcessing) {
      const timer = setTimeout(() => inputRef.current?.focus(), 100);
      return () => clearTimeout(timer);
    }
  }, [isProcessing]);

  // ======================================================================
  // 5. SEND MESSAGE HANDLER
  // ======================================================================
  const handleSend = async (overrideText?: string) => {
    const textToSend = overrideText || input;
   
    if (!textToSend.trim() || isProcessing || !backendConnected) return;
    if (textToSend.length > MAX_CHARS) {
      alert(`Message exceeds ${MAX_CHARS} character limit`);
      return;
    }

    // Thunder animation
    setIsThundering(true);
    setTimeout(() => setIsThundering(false), 500);

    // Clear input and hide suggestions
    setInput('');
    setShowSuggestions(false);

    // Send to backend
    try {
      await sendMessage(textToSend);
    } catch (error: any) {
      console.error('Send failed:', error);
    }
   
    // Refocus input
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  // ======================================================================
  // 6. STT (Speech-to-Text) Handler - FIXED PORT
  // ======================================================================
  const toggleRecording = async () => {
    if (!permissions.micEnabled) {
      alert('Microphone permission not enabled. Enable in Settings.');
      return;
    }

    if (!isRecording) {
      setIsRecording(true);
      try {
        // ✅ SYNCED: Using port 8000 consistent with main.py
        const res = await fetch(`http://127.0.0.1:8000/api/audio/transcribe`, { 
          method: 'POST' 
        });
        const data = await res.json();
        if (data.text) setInput(data.text);
      } catch (err) {
        console.error("STT Failed: Ensure Python backend is running on 8000");
      } finally {
        setIsRecording(false);
      }
    }
  };

  // ======================================================================
  // 7. COPY MESSAGE TO CLIPBOARD
  // ======================================================================
  const copyToClipboard = async (text: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (error) {
      console.error('Copy failed:', error);
    }
  };

  // ======================================================================
  // 8. MESSAGE FEEDBACK (Thumbs Up/Down)
  // ======================================================================
  const handleFeedback = async (messageId: string, feedback: 'up' | 'down') => {
    // In production, send feedback to backend for model improvement
    console.log(`Feedback for ${messageId}: ${feedback}`);
    try {
      await fetch('http://127.0.0.1:8000/api/chat/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messageId, feedback })
      });
    } catch (error) {
      console.warn('Feedback submission failed:', error);
    }
  };

  // ======================================================================
  // 9. TOGGLE TTS
  // ======================================================================
  const toggleTTS = () => {
    setIsMuted(!isMuted);
  };

  const isTyping = input.length > 0;
  const isPassive = mode === 'passive';
  const canSend = input.trim() && !isProcessing && !isRecording && backendConnected;

  return (
    <div className="h-full flex flex-col p-4 relative z-10 overflow-hidden">
     
      {/* ==================== HEADER: System Status & TTS ==================== */}
      <div className="flex justify-between items-center mb-6 px-2">
        <div className="flex items-center gap-3">
          <div className={`text-[10px] uppercase tracking-widest border rounded-full px-4 py-1.5 bg-black/40 backdrop-blur-sm flex items-center gap-2 shadow-lg ${
            backendConnected
              ? 'border-[#1f1f1f] text-gray-400'
              : 'border-red-500/30 text-red-400'
          }`}>
            <Cpu size={12} className={isPassive ? 'text-[#bc13fe]' : 'text-[#00f3ff]'} />
            Qwen 3.5 {isPassive ? '(PASSIVE)' : '(ACTIVE)'}
          </div>
         
          {/* Connection Status */}
          <div className={`flex items-center gap-1.5 text-[9px] uppercase tracking-widest ${
            backendConnected ? 'text-gray-600' : 'text-red-400'
          }`}>
            <div className={`h-1.5 w-1.5 rounded-full ${
              backendConnected
                ? isProcessing ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'
                : 'bg-red-500 animate-pulse'
            }`} />
            {backendConnected ? (isProcessing ? 'Processing' : 'Online') : 'Offline'}
          </div>
        </div>
       
        {/* TTS Toggle */}
        <button
          onClick={toggleTTS}
          disabled={!backendConnected}
          className={`p-2 rounded-full border transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed ${
            isMuted
              ? 'border-gray-700 text-gray-600 hover:bg-white/5'
              : 'border-[#00f3ff]/30 text-[#00f3ff] bg-[#00f3ff]/10 shadow-[0_0_10px_rgba(0,243,255,0.2)]'
          }`}
          title={isMuted ? "Unmute Voice Output" : "Mute Voice Output"}
        >
          {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
        </button>
      </div>

      {/* ==================== OFFLINE WARNING ==================== */}
      {!backendConnected && (
        <div className="mx-2 mb-4 p-3 rounded-lg border border-red-500/30 bg-red-900/20 flex items-center gap-2 text-red-400 text-xs animate-in slide-in-from-top-2">
          <AlertCircle size={14} />
          <span>AI Core Offline. Check Python backend connection.</span>
        </div>
      )}

      {/* ==================== MESSAGE HISTORY VIEWPORT ==================== */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto gloomy-scroll p-4 space-y-6"
      >
        {/* Welcome Banner (Only on first message) */}
        {messages.length <= 1 && (
          <div className="flex justify-center mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="text-center max-w-lg">
              <div className="text-[10px] text-gray-500 uppercase tracking-widest border border-[#1f1f1f] rounded-full px-4 py-1.5 bg-black/40 backdrop-blur-sm flex items-center gap-2 shadow-lg mb-4">
                <Sparkles size={12} className="text-[#00f3ff]" />
                Sovereign Vault Online
              </div>
              <h2 className="text-lg font-bold text-white mb-2">
                Welcome to HackT, Operator
              </h2>
              <p className="text-xs text-gray-400">
                Your local AI security agent is ready. Ask about code vulnerabilities,
                security best practices, or request screen analysis.
              </p>
              <div className="mt-4 flex items-center justify-center gap-4 text-[9px] text-gray-600">
                <span className="flex items-center gap-1">
                  <Keyboard size={10} /> Ctrl+K to focus
                </span>
                <span className="flex items-center gap-1">
                  <Keyboard size={10} /> Ctrl+Enter to send
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Render Messages (Memoized) */}
        {messages.filter(m => m.id !== 'system-init').map((msg, _index) => (
          <MessageItem
            key={msg.id}
            msg={msg}
            isPassive={isPassive}
            copiedMessageId={copiedMessageId}
            onCopy={copyToClipboard}
            onFeedback={handleFeedback}
          />
        ))}
       
        {/* Processing Indicator */}
        {isProcessing && (
          <div className="flex justify-start animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className={`max-w-[85%] rounded-xl p-5 panel-3d shadow-xl ${
              isPassive ? 'border-[#bc13fe]/40' : 'border-[#00f3ff]/40'
            }`}>
              <div className="flex items-center gap-3">
                <div className="flex gap-1">
                  <div className={`w-2 h-2 rounded-full ${
                    isPassive ? 'bg-[#bc13fe]' : 'bg-[#00f3ff]'
                  } animate-bounce`} style={{ animationDelay: '0ms' }} />
                  <div className={`w-2 h-2 rounded-full ${
                    isPassive ? 'bg-[#bc13fe]' : 'bg-[#00f3ff]'
                  } animate-bounce`} style={{ animationDelay: '150ms' }} />
                  <div className={`w-2 h-2 rounded-full ${
                    isPassive ? 'bg-[#bc13fe]' : 'bg-[#00f3ff]'
                  } animate-bounce`} style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-xs text-gray-400 uppercase tracking-widest">
                  Analyzing...
                </span>
              </div>
            </div>
          </div>
        )}
       
        <div ref={endOfMessagesRef} className="h-4" />
      </div>

      {/* ==================== SMART SUGGESTIONS BAR ==================== */}
      {showSuggestions && suggestions.length > 0 && !isProcessing && backendConnected && (
        <div className="mt-3 px-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-center justify-between text-[9px] text-gray-500 uppercase tracking-widest mb-2">
            <div className="flex items-center gap-1">
              <Sparkles size={10} />
              <span>Suggested Actions</span>
            </div>
            <button
              onClick={() => setShowSuggestions(false)}
              className="hover:text-white transition-colors"
            >
              <X size={10} />
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.id}
                onClick={() => handleSend(suggestion.text)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[10px] uppercase tracking-widest transition-all duration-300 hover:scale-105 ${
                  suggestion.type === 'ide'
                    ? 'border-[#bc13fe]/30 text-[#bc13fe] hover:bg-[#bc13fe]/10'
                    : suggestion.type === 'history'
                    ? 'border-[#00f3ff]/30 text-[#00f3ff] hover:bg-[#00f3ff]/10'
                    : 'border-[#1f1f1f] text-gray-400 hover:bg-white/5'
                }`}
              >
                {suggestion.icon}
                <span className="max-w-[200px] truncate">{suggestion.text}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ==================== REACTIVE INPUT AREA ==================== */}
      <div className="mt-3 shrink-0 px-2 pb-2 relative flex flex-col gap-2">
       
        {/* Live Context Telemetry Bar */}
        {mode === 'passive' && permissions.ideIntegration && activeContext.file && (
          <div className="flex items-center justify-between px-2 opacity-80 transition-opacity hover:opacity-100">
            <div className="flex items-center gap-2 text-[10px] font-mono tracking-widest text-gray-400">
              <Activity size={12} className="text-[#bc13fe] animate-pulse" />
              <span className="uppercase">Active Context:</span>
              <span className="px-2 py-0.5 rounded bg-white/5 border border-[#bc13fe]/30 text-[#bc13fe]">
                {activeContext.file}
              </span>
            </div>
            {activeContext.lastModified && (
              <div className="text-[9px] text-gray-600">
                Modified: {activeContext.lastModified}
              </div>
            )}
          </div>
        )}

        {/* Glow Underlay for Thunder Effect */}
        <div className={`absolute inset-0 rounded-xl transition-opacity duration-300 ${
          isThundering ? 'opacity-100' : 'opacity-0'
        } pointer-events-none z-0`}>
          <div className={`w-full h-full rounded-xl blur-md ${
            isPassive ? 'bg-[#bc13fe]/30' : 'bg-[#00f3ff]/30'
          }`}></div>
        </div>

        {/* Input Form */}
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="relative flex items-center group z-10 w-full">
          <Terminal className={`absolute left-5 transition-colors duration-300 ${
            isTyping
              ? isPassive ? 'text-[#bc13fe]' : 'text-[#00f3ff]'
              : 'text-gray-500'
          }`} size={18} />
         
          <input
            ref={inputRef}
            type="text"
            value={isRecording ? 'Listening to operator...' : input}
            onChange={(e) => setInput(e.target.value.slice(0, MAX_CHARS))}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={isRecording || isProcessing || !backendConnected}
            placeholder={
              !backendConnected
                ? 'AI Core Offline...'
                : isRecording
                  ? 'Listening...'
                  : `Query Local Vault... ${isPassive ? '(OCR & Sockets Monitoring)' : ''}`
            }
            className={`w-full input-3d rounded-xl py-5 pl-14 pr-32 text-white focus:outline-none font-mono text-sm placeholder-gray-600 shadow-2xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed ${
              isTyping ? 'typing-glow border-opacity-100' : 'border-opacity-50'
            } ${isRecording ? 'border-red-500/50 bg-red-950/10 text-red-400' : ''} ${
              isProcessing || !backendConnected ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          />
         
          <div className="absolute right-3 flex items-center gap-1">
            {/* Microphone (STT) Toggle */}
            <button
              type="button"
              onClick={toggleRecording}
              disabled={isProcessing || !backendConnected || !permissions.micEnabled}
              className={`p-3 rounded-lg flex items-center justify-center transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed ${
                isRecording
                  ? 'bg-red-500/20 text-red-500 shadow-[0_0_15px_rgba(239,68,68,0.4)] animate-pulse'
                  : 'bg-transparent text-gray-500 hover:text-white hover:bg-white/5'
              }`}
              title={permissions.micEnabled ? "Voice Input" : "Enable Mic in Settings"}
            >
              <Mic size={18} />
            </button>

            {/* Send Button */}
            <button
              type="submit"
              disabled={!canSend}
              className={`p-3 rounded-lg flex items-center justify-center transition-all duration-300 ${
                !canSend
                  ? 'bg-transparent text-gray-600 cursor-not-allowed'
                  : `bg-[#1f1f1f] ${
                    isPassive
                      ? 'text-[#bc13fe] hover:bg-[#bc13fe]/10 hover:shadow-[0_0_15px_rgba(188,19,254,0.3)]'
                      : 'text-[#00f3ff] hover:bg-[#00f3ff]/10 hover:shadow-[0_0_15px_rgba(0,243,255,0.3)]'
                  }`
              } ${isThundering ? 'scale-110' : 'active:scale-95'}`}
              title="Send Message"
            >
              {isThundering ? (
                <Zap size={18} className="animate-pulse" />
              ) : isProcessing ? (
                <RefreshCw size={18} className="animate-spin" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </div>
        </form>

        {/* Input Helper Text */}
        <div className="flex justify-between items-center px-2">
          <div className="text-[8px] uppercase tracking-widest">
            {isRecording ? (
              <span className="text-red-400 flex items-center gap-1">
                <AlertCircle size={8} /> Recording... Press again to stop
              </span>
            ) : !backendConnected ? (
              <span className="text-red-400">Backend Offline</span>
            ) : !permissions.micEnabled ? (
              <span className="text-gray-500">Enable mic for voice input</span>
            ) : (
              <span className="text-gray-600">Press Enter to send • Shift+Enter for new line</span>
            )}
          </div>
          <div className={`text-[8px] uppercase tracking-widest ${
            charCount > MAX_CHARS * 0.9 ? 'text-red-400' : 'text-gray-600'
          }`}>
            {charCount}/{MAX_CHARS}
          </div>
        </div>
      </div>
    </div>
  );
}