import { describe, expect, it, vi } from 'vitest';
import { getRetentionSessionId } from '../retentionFunnel';

describe('getRetentionSessionId', () => {
  it('creates one versioned browser session id and reuses it', () => {
    const values = new Map<string, string>();
    const storage: Storage = {
      get length() { return values.size; },
      clear: () => values.clear(),
      getItem: (key) => values.get(key) ?? null,
      key: (index) => [...values.keys()][index] ?? null,
      removeItem: (key) => { values.delete(key); },
      setItem: (key, value) => { values.set(key, value); },
    };
    const createId = vi.fn(() => 'session-generated-123456');

    expect(getRetentionSessionId(storage, createId)).toBe('session-generated-123456');
    expect(getRetentionSessionId(storage, createId)).toBe('session-generated-123456');
    expect(createId).toHaveBeenCalledTimes(1);
    expect(values.get('dsa.retention.session.v1')).toBe('session-generated-123456');
  });

  it('keeps a stable in-memory id when browser storage is restricted', () => {
    const storage = {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
    } as unknown as Storage;
    const createId = vi.fn(() => 'session-fallback-123456');

    expect(getRetentionSessionId(storage, createId)).toBe('session-fallback-123456');
    expect(getRetentionSessionId(storage, createId)).toBe('session-fallback-123456');
    expect(createId).toHaveBeenCalledTimes(1);
  });
});
