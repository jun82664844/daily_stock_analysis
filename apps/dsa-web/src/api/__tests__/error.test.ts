import { describe, expect, it } from 'vitest';
import { parseApiError } from '../error';

describe('parseApiError rate limit metadata', () => {
  it('keeps retry_after_seconds from a top-level 429 response', () => {
    const parsed = parseApiError({
      response: {
        status: 429,
        data: {
          error: 'rate_limited',
          message: 'Too many requests.',
          retry_after_seconds: 37,
        },
      },
    });

    expect(parsed.status).toBe(429);
    expect(parsed.retryAfterSeconds).toBe(37);
  });

  it('keeps retry_after_seconds from a FastAPI detail payload', () => {
    const parsed = parseApiError({
      response: {
        status: 429,
        data: {
          detail: {
            error: 'rate_limited',
            message: 'Too many requests.',
            retry_after_seconds: 12,
          },
        },
      },
    });

    expect(parsed.retryAfterSeconds).toBe(12);
  });
});
