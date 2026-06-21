// @vitest-environment node

import type { UserConfig } from 'vite';
import { describe, expect, it } from 'vitest';
import viteConfig from '../../vite.config';

describe('vite build config', () => {
  it('keeps old static chunks so already-open pages can lazy-load reports after rebuilds', () => {
    const config = viteConfig as UserConfig;

    expect(config.build?.emptyOutDir).toBe(false);
  });
});
