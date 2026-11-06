// Browser-storage keys used before the project was renamed from VANTA to CHRONYX.
export const LEGACY_STORAGE_KEYS = {
  vantaEvents: 'chronyxEvents',
  vantaEventOutbox: 'chronyxEventOutbox',
  vantaReminders: 'chronyxReminders',
  vantaReminderOutbox: 'chronyxReminderOutbox',
  vantaProfilePicture: 'chronyxProfilePicture',
};

// Moves each old key's value to its new key, once, without ever overwriting newer data.
export function migrateLegacyStorage(store) {
  if (!store) return;
  for (const [legacyKey, key] of Object.entries(LEGACY_STORAGE_KEYS)) {
    try {
      const legacyValue = store.getItem(legacyKey);
      if (legacyValue === null) continue;
      if (store.getItem(key) === null) store.setItem(key, legacyValue);
      store.removeItem(legacyKey);
    } catch {
      // Storage can be unavailable or full; the app falls back to the service data.
    }
  }
}
