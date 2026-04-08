import { useState, useMemo } from 'react';
import { X, Check, AlertTriangle, Info, Code, Shield, Zap } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface CodeDiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: () => Promise<void> | void;
  originalCode: string;
  suggestedFix: string;
  threatLevel: 'safe' | 'medium' | 'high' | 'critical';
  source: string;
  vulnerability?: {
    type: string;
    description: string;
    mitigation: string;
    cwe_id?: string;
  };
}

export default function CodeDiffModal({
  isOpen,
  onClose,
  onApply,
  originalCode,
  suggestedFix,
  threatLevel,
  source,
  vulnerability
}: CodeDiffModalProps) {
  const [isApplying, setIsApplying] = useState(false);
  const [activeTab, setActiveTab] = useState<'diff' | 'explain'>('diff');

  if (!isOpen) return null;

  // ======================================================================
  // 1. THREAT-BASED STYLING
  // ======================================================================
  const getThreatStyles = useMemo(() => {
    switch (threatLevel) {
      case 'critical':
        return {
          border: 'border-[#ff003c]',
          bg: 'bg-red-950/30',
          text: 'text-[#ff003c]',
          shadow: 'shadow-[0_0_80px_rgba(255,0,60,0.3)]',
          glow: 'animate-pulse',
        };
      case 'high':
        return {
          border: 'border-[#ff003c]/70',
          bg: 'bg-red-950/20',
          text: 'text-[#ff003c]',
          shadow: 'shadow-[0_0_60px_rgba(255,0,60,0.2)]',
          glow: '',
        };
      case 'medium':
        return {
          border: 'border-[#ffb000]',
          bg: 'bg-yellow-950/20',
          text: 'text-[#ffb000]',
          shadow: 'shadow-[0_0_40px_rgba(255,176,0,0.2)]',
          glow: '',
        };
      default:
        return {
          border: 'border-[#00f3ff]/30',
          bg: 'bg-[#00f3ff]/10',
          text: 'text-[#00f3ff]',
          shadow: 'shadow-[0_0_40px_rgba(0,243,255,0.2)]',
          glow: '',
        };
    }
  }, [threatLevel]);

  const threatStyles = getThreatStyles;

  // ======================================================================
  // 2. LANGUAGE DETECTION FOR SYNTAX HIGHLIGHTING
  // ======================================================================
  const detectLanguage = (_code: string, filePath: string): string => {
    // Extract extension from file path
    const ext = filePath.split('.').pop()?.toLowerCase();
    
    const langMap: Record<string, string> = {
      'py': 'python',
      'js': 'javascript',
      'ts': 'typescript',
      'jsx': 'jsx',
      'tsx': 'tsx',
      'html': 'html',
      'css': 'css',
      'json': 'json',
      'md': 'markdown',
      'sh': 'bash',
      'rs': 'rust',
      'go': 'go',
      'java': 'java',
      'c': 'c',
      'cpp': 'cpp',
      'cs': 'csharp',
      'php': 'php',
      'rb': 'ruby',
    };
    
    return langMap[ext || ''] || 'plaintext';
  };

  const language = useMemo(() => detectLanguage(originalCode, source), [originalCode, source]);

  // ======================================================================
  // 3. APPLY FIX HANDLER (Tauri FS Integration)
  // ======================================================================
  const handleApplyFix = async () => {
    setIsApplying(true);
    try {
        await onApply(); // ✅ Call the parent's actual Tauri FS function
        onClose();
    } catch (error) {
        console.error('Failed to apply fix:', error);
    } finally {
        setIsApplying(false);
    }
    };

  // ======================================================================
  // 4. RENDER HELPERS
  // ======================================================================
  const getSeverityBadge = () => {
    const colors: Record<string, string> = {
      critical: 'bg-red-500/20 text-red-400 border-red-500/30',
      high: 'bg-red-500/20 text-red-400 border-red-500/30',
      medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      safe: 'bg-green-500/20 text-green-400 border-green-500/30',
    };
    return colors[threatLevel] || colors.safe;
  };

  // ======================================================================
  // 5. MAIN RENDER
  // ======================================================================
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#030305]/95 backdrop-blur-md p-4">
      {/* Backdrop Click to Close */}
      <div 
        className="absolute inset-0" 
        onClick={onClose}
        aria-hidden="true"
      />
      
      <div className={`relative w-full max-w-6xl panel-3d ${threatStyles.border} ${threatStyles.bg} ${threatStyles.shadow} rounded-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-300`}>
        
        {/* ==================== HEADER ==================== */}
        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-black/20">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${threatStyles.bg} ${threatStyles.border}`}>
              <AlertTriangle className={`${threatStyles.text} ${threatStyles.glow}`} size={24} />
            </div>
            <div>
              <h3 className={`text-lg font-bold ${threatStyles.text} flex items-center gap-2`}>
                Security Vulnerability Detected
                <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-widest border ${getSeverityBadge()}`}>
                  {threatLevel.toUpperCase()}
                </span>
              </h3>
              <p className="text-[10px] text-gray-400 font-mono truncate max-w-md" title={source}>
                {source}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            aria-label="Close modal"
          >
            <X size={20} className="text-gray-400 hover:text-white" />
          </button>
        </div>

        {/* ==================== TAB NAVIGATION ==================== */}
        <div className="flex border-b border-white/10 bg-black/10">
          <button
            onClick={() => setActiveTab('diff')}
            className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest transition-colors ${
              activeTab === 'diff'
                ? `${threatStyles.text} border-b-2 ${threatStyles.border}`
                : 'text-gray-500 hover:text-white'
            }`}
          >
            <Code size={14} className="inline mr-2" />
            Code Diff
          </button>
          <button
            onClick={() => setActiveTab('explain')}
            className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest transition-colors ${
              activeTab === 'explain'
                ? `${threatStyles.text} border-b-2 ${threatStyles.border}`
                : 'text-gray-500 hover:text-white'
            }`}
          >
            <Info size={14} className="inline mr-2" />
            Explanation
          </button>
        </div>

        {/* ==================== CONTENT AREA ==================== */}
        <div className="flex-1 overflow-y-auto gloomy-scroll p-6">
          
          {activeTab === 'diff' && (
            <div className="space-y-6">
              {/* Vulnerability Summary (if provided) */}
              {vulnerability && (
                <div className={`p-4 rounded-lg border ${threatStyles.border} ${threatStyles.bg}`}>
                  <div className="flex items-start gap-3">
                    <Shield className={threatStyles.text} size={18} />
                    <div>
                      <h4 className={`text-sm font-bold ${threatStyles.text} mb-1`}>
                        {vulnerability.type}
                      </h4>
                      <p className="text-xs text-gray-300 mb-2">{vulnerability.description}</p>
                      {vulnerability.cwe_id && (
                        <span className="text-[10px] text-gray-500 font-mono">
                          CWE-{vulnerability.cwe_id}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Side-by-Side Code Diff */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Original Code (Vulnerable) */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-gray-500 uppercase tracking-widest flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      Original Code
                    </div>
                    <span className="text-[10px] text-red-400 font-mono">VULNERABLE</span>
                  </div>
                  <div className="relative group">
                    <SyntaxHighlighter
                      style={oneDark}
                      language={language}
                      customStyle={{ 
                        background: 'rgba(255, 0, 60, 0.05)',
                        border: '1px solid rgba(255, 0, 60, 0.3)',
                        borderRadius: '0.5rem',
                        margin: 0,
                        padding: '1rem'
                      }}
                      showLineNumbers={true}
                      wrapLines={true}
                    >
                      {originalCode}
                    </SyntaxHighlighter>
                    {/* Vulnerable lines highlight overlay */}
                    <div className="absolute inset-0 pointer-events-none">
                      {/* In production: Use diff library to highlight specific lines */}
                      <div className="absolute top-0 left-0 right-0 h-6 bg-red-500/10 border-l-2 border-red-500" />
                    </div>
                  </div>
                </div>
                
                {/* Suggested Fix (Secure) */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-gray-500 uppercase tracking-widest flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      Suggested Fix
                    </div>
                    <span className="text-[10px] text-green-400 font-mono">SECURE</span>
                  </div>
                  <div className="relative group">
                    <SyntaxHighlighter
                      style={oneDark}
                      language={language}
                      customStyle={{ 
                        background: 'rgba(34, 197, 94, 0.05)',
                        border: '1px solid rgba(34, 197, 94, 0.3)',
                        borderRadius: '0.5rem',
                        margin: 0,
                        padding: '1rem'
                      }}
                      showLineNumbers={true}
                      wrapLines={true}
                    >
                      {suggestedFix}
                    </SyntaxHighlighter>
                    {/* Fixed lines highlight overlay */}
                    <div className="absolute inset-0 pointer-events-none">
                      {/* In production: Use diff library to highlight specific lines */}
                      <div className="absolute top-0 left-0 right-0 h-6 bg-green-500/10 border-l-2 border-green-500" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Diff Legend */}
              <div className="flex items-center justify-center gap-6 text-[10px] text-gray-500">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded bg-red-500/30 border border-red-500/50" />
                  <span>Removed/Vulnerable</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded bg-green-500/30 border border-green-500/50" />
                  <span>Added/Secure</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'explain' && vulnerability && (
            <div className="space-y-6">
              {/* Vulnerability Details */}
              <div className={`p-6 rounded-lg border ${threatStyles.border} ${threatStyles.bg}`}>
                <h4 className={`text-sm font-bold ${threatStyles.text} mb-4 flex items-center gap-2`}>
                  <AlertTriangle size={16} />
                  Vulnerability Analysis
                </h4>
                
                <div className="space-y-4 text-sm">
                  <div>
                    <h5 className="text-xs text-gray-400 uppercase tracking-widest mb-2">Type</h5>
                    <p className="text-white">{vulnerability.type}</p>
                  </div>
                  
                  <div>
                    <h5 className="text-xs text-gray-400 uppercase tracking-widest mb-2">Description</h5>
                    <p className="text-gray-300">{vulnerability.description}</p>
                  </div>
                  
                  {vulnerability.cwe_id && (
                    <div>
                      <h5 className="text-xs text-gray-400 uppercase tracking-widest mb-2">CWE Reference</h5>
                      <a 
                        href={`https://cwe.mitre.org/data/definitions/${vulnerability.cwe_id}.html`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#00f3ff] hover:underline text-xs font-mono"
                      >
                        CWE-{vulnerability.cwe_id} (MITRE)
                      </a>
                    </div>
                  )}
                  
                  <div>
                    <h5 className="text-xs text-gray-400 uppercase tracking-widest mb-2">Mitigation</h5>
                    <p className="text-gray-300">{vulnerability.mitigation}</p>
                  </div>
                </div>
              </div>

              {/* Security Best Practices */}
              <div className="panel-3d p-6 rounded-lg border border-white/10">
                <h4 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <Zap size={16} className="text-[#00f3ff]" />
                  Security Best Practices
                </h4>
                
                <ul className="space-y-3 text-sm text-gray-300">
                  <li className="flex items-start gap-2">
                    <Check size={14} className="text-green-400 mt-0.5" />
                    <span>Always validate and sanitize user input before execution</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Check size={14} className="text-green-400 mt-0.5" />
                    <span>Use parameterized queries or ORM methods instead of string concatenation</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Check size={14} className="text-green-400 mt-0.5" />
                    <span>Implement principle of least privilege for file/system access</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Check size={14} className="text-green-400 mt-0.5" />
                    <span>Regularly update dependencies to patch known vulnerabilities</span>
                  </li>
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'explain' && !vulnerability && (
            <div className="text-center py-12 text-gray-500">
              <Info size={48} className="mx-auto mb-4 opacity-50" />
              <p className="text-sm">No detailed explanation available for this vulnerability.</p>
              <p className="text-[10px] mt-2">Check the Code Diff tab for the suggested fix.</p>
            </div>
          )}
        </div>

        {/* ==================== FOOTER ACTIONS ==================== */}
        <div className="p-4 border-t border-white/10 bg-black/20 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-6 py-2.5 rounded-lg border border-white/20 text-gray-400 hover:bg-white/5 hover:text-white transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isApplying}
          >
            Dismiss
          </button>
          <button
            onClick={handleApplyFix}
            className={`px-6 py-2.5 rounded-lg ${threatStyles.border} ${threatStyles.text} hover:bg-white/10 transition-colors text-sm font-bold flex items-center gap-2 disabled:opacity-50 disabled:cursor-wait ${
              isApplying ? 'animate-pulse' : ''
            }`}
            disabled={isApplying}
          >
            {isApplying ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                Applying Fix...
              </>
            ) : (
              <>
                <Check size={16} />
                Apply Secure Fix
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}