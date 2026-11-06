import {createRoot} from 'react-dom/client';
import App from './App';
import './style.css';
import {migrateLegacyStorage} from './storage-migration.js';

// Carry browser-stored data over from releases named VANTA before anything reads it.
try {
  migrateLegacyStorage(window.localStorage);
} catch {
  // Storage access can be blocked; the app still works from the local service.
}

createRoot(document.getElementById('root')!).render(<App />);
