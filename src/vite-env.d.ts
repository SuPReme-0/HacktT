/// <reference types="vite/client" />

// ======================================================================
// ENVIRONMENT VARIABLES
// ======================================================================
interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_ANON_KEY: string;
  readonly VITE_APP_VERSION: string;
  readonly VITE_BACKEND_URL: string;
  // Add any other env vars here
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// ======================================================================
// ASSET TYPES
// ======================================================================
declare module '*.svg' {
  const content: React.FC<React.SVGProps<SVGElement>>;
  export default content;
}

declare module '*.png' {
  const content: string;
  export default content;
}

declare module '*.jpg' {
  const content: string;
  export default content;
}

declare module '*.gif' {
  const content: string;
  export default content;
}

declare module '*.mp3' {
  const content: string;
  export default content;
}

declare module '*.wav' {
  const content: string;
  export default content;
}

// ======================================================================
// TAURI TYPES
// ======================================================================
declare module '@tauri-apps/api/*' {
  const content: any;
  export default content;
}