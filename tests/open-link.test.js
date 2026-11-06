import test from 'node:test';
import assert from 'node:assert/strict';
import {openExternal, safeExternalUrl} from '../src/open-link.js';

test('only http and https links are considered safe', () => {
  assert.equal(safeExternalUrl('https://ctftime.org/event/1'), 'https://ctftime.org/event/1');
  assert.equal(safeExternalUrl('http://example.com'), 'http://example.com/');
  for (const bad of ['javascript:alert(1)', 'file:///etc/passwd', 'ftp://example.com', 'not a url', '', undefined]) {
    assert.equal(safeExternalUrl(bad), '', String(bad));
  }
});

test('opening a link posts the normalised URL to the local service', async () => {
  const calls = [];
  await openExternal('https://example.com/a b', async (path, options) => {
    calls.push([path, options.method, JSON.parse(options.body)]);
    return {ok: true};
  });
  assert.deepEqual(calls, [['/api/open', 'POST', {url: 'https://example.com/a%20b'}]]);
});

test('an unsafe link is rejected without contacting the service', async () => {
  let called = false;
  await assert.rejects(
    openExternal('javascript:alert(1)', async () => {
      called = true;
      return {ok: true};
    }),
    /not a valid web address/,
  );
  assert.equal(called, false);
});

test('service failures reject with a readable message', async () => {
  await assert.rejects(
    openExternal('https://example.com', async () => ({ok: false})),
    /system browser/,
  );
  await assert.rejects(
    openExternal('https://example.com', async () => {
      throw new TypeError('refused');
    }),
    /local service/,
  );
});
