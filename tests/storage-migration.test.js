import test from 'node:test';
import assert from 'node:assert/strict';
import {LEGACY_STORAGE_KEYS, migrateLegacyStorage} from '../src/storage-migration.js';

function memoryStore(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    values,
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test('every legacy key moves to its CHRONYX key and the old key is removed', () => {
  const store = memoryStore(Object.fromEntries(Object.keys(LEGACY_STORAGE_KEYS).map((key) => [key, `value:${key}`])));
  migrateLegacyStorage(store);
  for (const [legacyKey, key] of Object.entries(LEGACY_STORAGE_KEYS)) {
    assert.equal(store.getItem(key), `value:${legacyKey}`);
    assert.equal(store.getItem(legacyKey), null);
  }
});

test('newer CHRONYX data is never overwritten by an old value', () => {
  const store = memoryStore({vantaEvents: 'old', chronyxEvents: 'new'});
  migrateLegacyStorage(store);
  assert.equal(store.getItem('chronyxEvents'), 'new');
  assert.equal(store.getItem('vantaEvents'), null);
});

test('running the migration again changes nothing', () => {
  const store = memoryStore({vantaProfilePicture: 'data:image/jpeg;base64,AAAA'});
  migrateLegacyStorage(store);
  const snapshot = JSON.stringify([...store.values]);
  migrateLegacyStorage(store);
  assert.equal(JSON.stringify([...store.values]), snapshot);
});

test('unrelated keys such as the theme are left alone', () => {
  const store = memoryStore({theme: 'light', vantaEvents: '[]'});
  migrateLegacyStorage(store);
  assert.equal(store.getItem('theme'), 'light');
});

test('missing or failing storage never throws', () => {
  assert.doesNotThrow(() => migrateLegacyStorage(null));
  const broken = {
    getItem: () => {
      throw new Error('denied');
    },
  };
  assert.doesNotThrow(() => migrateLegacyStorage(broken));
});
