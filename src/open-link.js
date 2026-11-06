export function safeExternalUrl(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}

// Opens a web link in the system browser through the local service. Rejects with a
// user-readable message so the interface can show it instead of failing silently.
export async function openExternal(value, request = globalThis.fetch) {
  const url = safeExternalUrl(value);
  if (!url) throw new Error('That link is not a valid web address.');
  let response;
  try {
    response = await request('/api/open', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url}),
    });
  } catch {
    throw new Error('Could not reach the local service to open the link.');
  }
  if (!response.ok) throw new Error('Could not open the link in your system browser.');
}
