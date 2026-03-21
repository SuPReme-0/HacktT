import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useSystemStore } from '../store/systemStore';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { 
  Send, Terminal, Cpu, Zap, Mic, Volume2, VolumeX, 
  Code, Activity, Sparkles, History, Lightbulb, 
  RefreshCw, CheckCircle, AlertCircle, Copy, ThumbsUp, ThumbsDown
} from 'lucide-react';

// Suggestion types for smart recommendations
interface Suggestion {
  id: string;
  type: 'ide' | 'history' | 'context' | 'quick';
  text: string;
  icon: React.ReactNode;
  priority: number;
}

export default function ChatInterface() {
  const { 
    messages, 
    sendMessage, 
    mode, 
    isProcessing, 
    permissions,
    vaultSkills 
  } = useSystemStore();
  
  // Local States
  const [input, setInput] = useState('');
  const [isThundering, setIsThundering] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [typedMessage, setTypedMessage] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(true);
  
  // Telemetry from backend (will be populated from store in production)
  const [activeContext, setActiveContext] = useState<{
    file?: string;
    language?: string;
    lastModified?: string;
    recentChanges?: string[];
  }>({});

  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // ======================================================================
  // 1. AUTO-SCROLL TO LATEST MESSAGE
  // ======================================================================
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ======================================================================
  // 2. GENERATE SMART SUGGESTIONS
  // ======================================================================
  useEffect(() => {
    const generateSuggestions = () => {
      const newSuggestions: Suggestion[] = [];

      // IDE Context Suggestions (Passive Mode)
      if (mode === 'passive' && permissions.ideIntegration && activeContext.file) {
        newSuggestions.push({
          id: 'ide-1',
          type: 'ide',
          text: `Analyze ${activeContext.file} for vulnerabilities`,
          icon: <Code size={12} />,
          priority: 1
        });
        newSuggestions.push({
          id: 'ide-2',
          type: 'ide',
          text: 'Optimize current file performance',
          icon: <Zap size={12} />,
          priority: 2
        });
      }

      // Recent History Suggestions
      if (messages.length > 2) {
        const lastUserMessage = messages.filter(m => m.sender === 'user').slice(-1)[0];
        if (lastUserMessage) {
          newSuggestions.push({
            id: 'hist-1',
            type: 'history',
            text: `Continue: ${lastUserMessage.text.slice(0, 40)}...`,
            icon: <History size={12} />,
            priority: 3
          });
        }
      }

      // Context-Aware Suggestions (Vault Skills)
      if (vaultSkills.length > 0) {
        const randomSkill = vaultSkills[Math.floor(Math.random() * vaultSkills.length)];
        newSuggestions.push({
          id: 'ctx-1',
          type: 'context',
          text: `Explain ${randomSkill.chapter} concepts`,
          icon: <Lightbulb size={12} />,
          priority: 4
        });
      }

      // Quick Action Suggestions
      newSuggestions.push(
        {
          id: 'quick-1',
          type: 'quick',
          text: 'Scan current screen for threats',
          icon: <Activity size={12} />,
          priority: 5
        },
        {
          id: 'quick-2',
          type: 'quick',
          text: 'Show security best practices',
          icon: <Sparkles size={12} />,
          priority: 6
        }
      );

      setSuggestions(newSuggestions.sort((a, b) => a.priority - b.priority).slice(0, 4));
    };

    generateSuggestions();
  }, [mode, permissions.ideIntegration, activeContext, messages, vaultSkills]);

  // ======================================================================
  // 3. TYPING ANIMATION FOR AI RESPONSES
  // ======================================================================
  const typeMessage = useCallback((fullText: string, speed: number = 10) => {
    let currentIndex = 0;
    setTypedMessage('');
    
    const typeInterval = setInterval(() => {
      if (currentIndex < fullText.length) {
        setTypedMessage(prev => prev + fullText[currentIndex]);
        currentIndex++;
      } else {
        clearInterval(typeInterval);
        setTypedMessage(fullText);
      }
    }, speed);

    return () => clearInterval(typeInterval);
  }, []);

  // ======================================================================
  // 4. SEND MESSAGE HANDLER
  // ======================================================================
  const handleSend = async (e?: React.FormEvent, overrideText?: string) => {
    e?.preventDefault();
    const textToSend = overrideText || input;
    
    if (!textToSend.trim() || isProcessing) return;

    // Thunder animation
    setIsThundering(true);
    setTimeout(() => setIsThundering(false), 500);

    // Clear input and hide suggestions
    setInput('');
    setShowSuggestions(false);

    // Send to backend
    await sendMessage(textToSend);
    
    // Refocus input
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  // ======================================================================
  // 5. STT (Speech-to-Text) Handler
  // ======================================================================
  const toggleRecording = async () => {
    if (!isRecording) {
      // In production, this would trigger Tauri invoke for Faster-Whisper
      setIsRecording(true);
      setInput('');
      
      // Simulate listening timeout (replace with actual STT callback)
      setTimeout(() => {
        setIsRecording(false);
        // In production: const transcribed = await invoke('get_stt_result');
        // setInput(transcribed);
      }, 5000);
    } else {
      setIsRecording(false);
    }
  };

  // ======================================================================
  // 6. COPY MESSAGE TO CLIPBOARD
  // ======================================================================
  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    // Show toast notification (implement in production)
  };

  // ======================================================================
  // 7. MESSAGE FEEDBACK (Thumbs Up/Down)
  // ======================================================================
  const handleFeedback = async (messageId: string, feedback: 'up' | 'down') => {
    // In production, send feedback to backend for model improvement
    console.log(`Feedback for ${messageId}: ${feedback}`);
  };

  const isTyping = input.length > 0;
  const isPassive = mode === 'passive';

  return (
    <div className="h-full flex flex-col p-4 relative z-10 overflow-hidden">
      
      {/* ==================== HEADER: System Status & TTS ==================== */}
      <div className="flex justify-between items-center mb-6 px-2">
        <div className="flex items-center gap-3">
          <div className="text-[10px] text-gray-500 uppercase tracking-widest border border-[#1f1f1f] rounded-full px-4 py-1.5 bg-black/40 backdrop-blur-sm flex items-center gap-2 shadow-lg">
            <Cpu size={12} className={isPassive ? 'text-[#bc13fe]' : 'text-[#00f3ff]'} />
            Qwen 3.5 Engine {isPassive ? '(PASSIVE)' : '(ACTIVE)'}
          </div>
          
          {/* Connection Status */}
          <div className="flex items-center gap-1.5 text-[9px] text-gray-600 uppercase tracking-widest">
            <div className={`h-1.5 w-1.5 rounded-full ${
              isProcessing ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'
            }`} />
            {isProcessing ? 'Processing' : 'Online'}
          </div>
        </div>
        
        {/* TTS Toggle */}
        <button 
          onClick={() => setIsMuted(!isMuted)}
          className={`p-2 rounded-full border transition-all duration-300 ${
            isMuted 
              ? 'border-gray-700 text-gray-600 hover:bg-white/5' 
              : 'border-[#00f3ff]/30 text-[#00f3ff] bg-[#00f3ff]/10 shadow-[0_0_10px_rgba(0,243,255,0.2)]'
          }`}
          title={isMuted ? "Unmute Voice Output" : "Mute Voice Output"}
        >
          {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
        </button>
      </div>

      {/* ==================== MESSAGE HISTORY VIEWPORT ==================== */}
      <div 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto gloomy-scroll p-4 space-y-6"
      >
        {/* Welcome Banner (Only on first message) */}
        {messages.length === 1 && (
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
            </div>
          </div>
        )}

        {/* Render Messages */}
        {messages.filter(m => m.id !== 'init').map((msg, index) => (
          <div 
            key={msg.id} 
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-forwards`}
            style={{ animationDelay: `${Math.min(index * 50, 300)}ms` }}
          >
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
                          <div className="relative group/code my-3 rounded-lg overflow-hidden">
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              {...props}
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                            <button
                              onClick={() => copyToClipboard(String(children))}
                              className="absolute top-2 right-2 p-1.5 rounded bg-white/10 opacity-0 group-hover/code:opacity-100 transition-opacity hover:bg-white/20"
                            >
                              <Copy size={14} className="text-white" />
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
                    onClick={() => copyToClipboard(msg.text)}
                    className="p-1.5 rounded hover:bg-white/5 text-gray-500 hover:text-white transition-colors"
                    title="Copy response"
                  >
                    <Copy size={12} />
                  </button>
                  <button
                    onClick={() => handleFeedback(msg.id, 'up')}
                    className="p-1.5 rounded hover:bg-white/5 text-gray-500 hover:text-green-400 transition-colors"
                    title="Helpful"
                  >
                    <ThumbsUp size={12} />
                  </button>
                  <button
                    onClick={() => handleFeedback(msg.id, 'down')}
                    className="p-1.5 rounded hover:bg-white/5 text-gray-500 hover:text-red-400 transition-colors"
                    title="Not helpful"
                  >
                    <ThumbsDown size={12} />
                  </button>
                </div>
              )}
            </div>
          </div>
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
      {showSuggestions && suggestions.length > 0 && !isProcessing && (
        <div className="mt-3 px-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-center gap-2 text-[9px] text-gray-500 uppercase tracking-widest mb-2">
            <Sparkles size={10} />
            <span>Suggested Actions</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.id}
                onClick={() => handleSend(undefined, suggestion.text)}
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
        {mode === 'passive' && permissions.ideIntegration && (
          <div className="flex items-center justify-between px-2 opacity-80 transition-opacity hover:opacity-100">
            <div className="flex items-center gap-2 text-[10px] font-mono tracking-widest text-gray-400">
              <Activity size={12} className="text-[#bc13fe] animate-pulse" />
              <span className="uppercase">Active Context:</span>
              <span className="px-2 py-0.5 rounded bg-white/5 border border-[#bc13fe]/30 text-[#bc13fe]">
                {activeContext.file || 'No file detected'}
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
        <form onSubmit={handleSend} className="relative flex items-center group z-10 w-full">
          <Terminal className={`absolute left-5 transition-colors duration-300 ${
            isTyping 
              ? isPassive ? 'text-[#bc13fe]' : 'text-[#00f3ff]'
              : 'text-gray-500'
          }`} size={18} />
          
          <input 
            ref={inputRef}
            type="text"
            value={isRecording ? 'Listening to operator...' : input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={isRecording || isProcessing}
            placeholder={
              isRecording 
                ? 'Listening...' 
                : `Query Local Vault... ${isPassive ? '(OCR & Sockets Monitoring)' : ''}`
            }
            className={`w-full input-3d rounded-xl py-5 pl-14 pr-32 text-white focus:outline-none font-mono text-sm placeholder-gray-600 shadow-2xl transition-all duration-300 ${
              isTyping ? 'typing-glow border-opacity-100' : 'border-opacity-50'
            } ${isRecording ? 'border-red-500/50 bg-red-950/10 text-red-400' : ''} ${
              isProcessing ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          />
          
          <div className="absolute right-3 flex items-center gap-1">
            {/* Microphone (STT) Toggle */}
            <button 
              type="button"
              onClick={toggleRecording}
              disabled={isProcessing}
              className={`p-3 rounded-lg flex items-center justify-center transition-all duration-300 ${
                isRecording 
                  ? 'bg-red-500/20 text-red-500 shadow-[0_0_15px_rgba(239,68,68,0.4)] animate-pulse' 
                  : 'bg-transparent text-gray-500 hover:text-white hover:bg-white/5'
              } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
              title="Voice Input"
            >
              <Mic size={18} />
            </button>

            {/* Send Button */}
            <button 
              type="submit" 
              disabled={(!input.trim() && !isRecording) || isProcessing}
              className={`p-3 rounded-lg flex items-center justify-center transition-all duration-300 ${
                (!input.trim() && !isRecording) || isProcessing
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
          <div className="text-[8px] text-gray-600 uppercase tracking-widest">
            {isRecording ? (
              <span className="text-red-400 flex items-center gap-1">
                <AlertCircle size={8} /> Recording... Press again to stop
              </span>
            ) : (
              <span>Press Enter to send • Shift+Enter for new line</span>
            )}
          </div>
          <div className="text-[8px] text-gray-600 uppercase tracking-widest">
            {input.length}/1000
          </div>
        </div>
      </div>
    </div>
  );
}