import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles/globals.css';

// ======================================================================
// 1. ERROR HANDLING FOR ROOT RENDER
// ======================================================================
const rootElement = document.getElementById('root');
if (!rootElement) {
  console.error('Fatal: Root element not found');
  throw new Error('Root element not found');
}

// ======================================================================
// 2. REACT 18 ROOT CREATION
// ======================================================================
const root = ReactDOM.createRoot(rootElement);

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);