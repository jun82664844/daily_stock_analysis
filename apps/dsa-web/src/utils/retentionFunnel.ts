const RETENTION_SESSION_STORAGE_KEY = 'dsa.retention.session.v1';
const SESSION_ID_PATTERN = /^[A-Za-z0-9._:-]{12,128}$/;

let fallbackSessionId: string | null = null;

function defaultSessionId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }
  return `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`;
}

export function getRetentionSessionId(
  storage: Pick<Storage, 'getItem' | 'setItem'>,
  createId: () => string = defaultSessionId,
): string {
  if (fallbackSessionId) {
    return fallbackSessionId;
  }

  try {
    const existing = storage.getItem(RETENTION_SESSION_STORAGE_KEY);
    if (existing && SESSION_ID_PATTERN.test(existing)) {
      return existing;
    }
  } catch {
    fallbackSessionId = createId();
    return fallbackSessionId;
  }

  const created = createId();
  try {
    storage.setItem(RETENTION_SESSION_STORAGE_KEY, created);
  } catch {
    fallbackSessionId = created;
  }
  return created;
}
