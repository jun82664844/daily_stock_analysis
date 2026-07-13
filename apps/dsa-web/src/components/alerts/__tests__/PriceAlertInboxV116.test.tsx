import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PriceAlertInboxV116 from '../PriceAlertInboxV116';

const { current, alertEvents, markAlertEventRead, markAllAlertEventsRead } = vi.hoisted(() => ({
  current: vi.fn(), alertEvents: vi.fn(), markAlertEventRead: vi.fn(), markAllAlertEventsRead: vi.fn(),
}));

vi.mock('../../../api/platform', () => ({
  PLATFORM_SESSION_CHANGED_EVENT: 'dsa-platform-session-changed',
  platformApi: { current, alertEvents, markAlertEventRead, markAllAlertEventsRead },
}));

const feed = { userId: 7, total: 1, unread: 1, aiUsed: false, items: [{
  id: 81, stockCode: 'AAPL', ruleType: 'price_above', direction: 'above', value: 201.25,
  threshold: 200, source: 'us_quote', observedAt: '2026-07-13T01:30:00', readAt: null, aiUsed: false,
}] };

describe('PriceAlertInboxV116', () => {
  beforeEach(() => {
    current.mockReset(); alertEvents.mockReset(); markAlertEventRead.mockReset(); markAllAlertEventsRead.mockReset();
    current.mockResolvedValue({ user: { id: 7, email: 'a@example.com' }, quota: {} });
    alertEvents.mockResolvedValue(feed);
    markAlertEventRead.mockResolvedValue({ ...feed, unread: 0, items: [] });
    markAllAlertEventsRead.mockResolvedValue({ ...feed, unread: 0, items: [] });
  });

  it('does not request private events for a guest', async () => {
    current.mockResolvedValue(null);
    render(<PriceAlertInboxV116 language="zh" />);
    await waitFor(() => expect(current).toHaveBeenCalled());
    expect(alertEvents).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '到价提醒收件箱' })).not.toBeInTheDocument();
  });

  it('shows unread events and marks one or all as read', async () => {
    render(<PriceAlertInboxV116 language="zh" />);
    const button = await screen.findByRole('button', { name: '到价提醒收件箱，1 条未读' });
    fireEvent.click(button);
    expect(await screen.findByText('AAPL')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '标记 AAPL 提醒为已读' }));
    await waitFor(() => expect(markAlertEventRead).toHaveBeenCalledWith(81));
  });

  it('refreshes identity after the platform session changes', async () => {
    render(<PriceAlertInboxV116 language="en" />);
    await screen.findByRole('button', { name: 'Price alert inbox, 1 unread' });
    current.mockResolvedValue({ user: { id: 8, email: 'b@example.com' }, quota: {} });
    alertEvents.mockResolvedValue({ ...feed, userId: 8, unread: 0, items: [] });
    window.dispatchEvent(new Event('dsa-platform-session-changed'));
    await waitFor(() => expect(current).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('button', { name: 'Price alert inbox' })).toBeInTheDocument();
  });
});
