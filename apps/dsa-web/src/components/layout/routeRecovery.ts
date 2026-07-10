const ROUTE_RECOVERY_PARAM = 'dsa_route_reload';

const routeChunkErrorMarkers = [
  'failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'importing a module script failed',
  'chunkloaderror',
  'loading chunk',
] as const;

const getErrorText = (error: unknown): string => {
  if (error instanceof Error) {
    return `${error.name} ${error.message} ${error.stack ?? ''}`;
  }
  return String(error ?? '');
};

export const isRecoverableRouteChunkError = (error: unknown): boolean => {
  const message = getErrorText(error).toLowerCase();
  return routeChunkErrorMarkers.some((marker) => message.includes(marker));
};

export const buildRouteRecoveryUrl = (currentHref: string, timestamp = Date.now()): string => {
  const url = new URL(currentHref, window.location.origin);
  url.searchParams.set(ROUTE_RECOVERY_PARAM, String(timestamp));
  return url.toString();
};

export const getRouteChunkReloadKey = (error: unknown, prefix: string): string => {
  const message = getErrorText(error);
  const assetMatch = message.match(/\/assets\/[^\s'")]+/i)?.[0];
  const signature = assetMatch ?? message.slice(0, 180);
  return `${prefix}${signature}`;
};
