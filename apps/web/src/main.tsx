import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { FullScreenLoading } from './FullScreenLoading';
import { ToastViewport } from './Toast';
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ToastViewport />
    <App />
    <FullScreenLoading />
  </React.StrictMode>,
);
