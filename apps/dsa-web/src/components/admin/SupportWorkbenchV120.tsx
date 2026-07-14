import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Inbox, RefreshCw, Send } from 'lucide-react';
import {
  supportApi,
  type SupportStatus,
  type SupportTicketDetail,
  type SupportTicketSummary,
} from '../../api/support';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import { Card, InlineAlert } from '../common';

const TEXT = {
  zh: {
    title: '客服工单', subtitle: '人工处理队列；不启用 AI 自动回复，不提供投资建议。', filter: '工单状态',
    all: '全部', open: '待处理', inProgress: '处理中', closed: '已关闭', unread: '未读', refresh: '刷新工单',
    empty: '当前筛选条件下没有工单。', select: '选择工单查看对话和处理状态。', reply: '管理员回复',
    replyPlaceholder: '填写产品支持答复，不要索取密码或 API Key。', send: '发送回复', sending: '发送中',
    markOpen: '标记待处理', markProgress: '标记处理中', markClosed: '标记已关闭', user: '用户', admin: '客服',
    loadError: '客服队列加载失败', actionError: '客服处理失败',
  },
  en: {
    title: 'Support tickets', subtitle: 'Human-operated queue. AI auto-replies and investment advice are disabled.', filter: 'Ticket status',
    all: 'All', open: 'Open', inProgress: 'In progress', closed: 'Closed', unread: 'Unread', refresh: 'Refresh support tickets',
    empty: 'No tickets match this filter.', select: 'Select a ticket to review the conversation and status.', reply: 'Administrator reply',
    replyPlaceholder: 'Provide product support. Never request passwords or API keys.', send: 'Send reply', sending: 'Sending',
    markOpen: 'Mark open', markProgress: 'Mark in progress', markClosed: 'Mark closed', user: 'User', admin: 'Support',
    loadError: 'Failed to load support queue', actionError: 'Support action failed',
  },
} as const;

function errorText(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'parsedError' in error) {
    const parsed = (error as { parsedError?: { message?: string } }).parsedError;
    if (parsed?.message) return parsed.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function summaryFromDetail(ticket: SupportTicketDetail): SupportTicketSummary {
  const { messages: _messages, ...summary } = ticket;
  void _messages;
  return summary;
}

function formatTime(value: string | null, language: 'zh' | 'en'): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(date);
}

const SupportWorkbenchV120 = () => {
  const { language } = useUiLanguage();
  const text = TEXT[language];
  const [filter, setFilter] = useState<SupportStatus | 'all'>('all');
  const [tickets, setTickets] = useState<SupportTicketSummary[]>([]);
  const [selected, setSelected] = useState<SupportTicketDetail | null>(null);
  const [reply, setReply] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadQueue = useCallback(async (statusFilter: SupportStatus | 'all') => {
    setLoading(true);
    setError(null);
    try {
      const response = await supportApi.adminListTickets(statusFilter);
      setTickets(response.tickets);
      if (selected && !response.tickets.some((ticket) => ticket.id === selected.id)) {
        setSelected(null);
      }
    } catch (nextError) {
      setError(errorText(nextError, text.loadError));
    } finally {
      setLoading(false);
    }
  }, [selected, text.loadError]);

  useEffect(() => {
    void loadQueue(filter);
  }, [filter, loadQueue]);

  const upsert = (ticket: SupportTicketDetail) => {
    const summary = summaryFromDetail(ticket);
    setTickets((current) => [summary, ...current.filter((item) => item.id !== ticket.id)]);
  };

  const openTicket = async (ticketId: number) => {
    setError(null);
    try {
      const ticket = await supportApi.adminGetTicket(ticketId);
      setSelected(ticket);
      upsert(ticket);
    } catch (nextError) {
      setError(errorText(nextError, text.loadError));
    }
  };

  const sendReply = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const ticket = await supportApi.adminAddMessage(selected.id, reply.trim());
      setSelected(ticket);
      upsert(ticket);
      setReply('');
    } catch (nextError) {
      setError(errorText(nextError, text.actionError));
    } finally {
      setBusy(false);
    }
  };

  const updateStatus = async (status: SupportStatus) => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const ticket = await supportApi.adminUpdateStatus(selected.id, status);
      setSelected(ticket);
      upsert(ticket);
    } catch (nextError) {
      setError(errorText(nextError, text.actionError));
    } finally {
      setBusy(false);
    }
  };

  const statusLabel = (status: SupportStatus) => status === 'open' ? text.open : status === 'in_progress' ? text.inProgress : text.closed;

  return (
    <Card className="rounded-lg" padding="none">
      <div className="flex flex-col gap-4 border-b border-border/70 px-5 py-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-foreground">{text.title}</h2>
          <p className="mt-1 text-sm text-secondary-text">{text.subtitle}</p>
        </div>
        <label className="block text-sm font-medium text-foreground">
          <span className="mb-1.5 block">{text.filter}</span>
          <select className="input-base min-w-44" aria-label={text.filter} value={filter} onChange={(event) => setFilter(event.target.value as SupportStatus | 'all')}>
            <option value="all">{text.all}</option>
            <option value="open">{text.open}</option>
            <option value="in_progress">{text.inProgress}</option>
            <option value="closed">{text.closed}</option>
          </select>
        </label>
        <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void loadQueue(filter)} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />{text.refresh}
        </button>
      </div>
      {error ? <div className="px-5 pt-4"><InlineAlert variant="danger" message={error} /></div> : null}
      <div className="grid min-w-0 xl:grid-cols-[minmax(17rem,0.75fr)_minmax(0,1.25fr)]">
        <div className="min-w-0 border-b border-border/70 xl:border-b-0 xl:border-r">
          <div className="max-h-[34rem] divide-y divide-border/60 overflow-y-auto">
            {!loading && tickets.length === 0 ? <p className="px-5 py-10 text-center text-sm text-secondary-text">{text.empty}</p> : null}
            {tickets.map((ticket) => (
              <button key={ticket.id} type="button" onClick={() => void openTicket(ticket.id)} className={cn('flex w-full min-w-0 items-start gap-3 px-5 py-4 text-left transition-colors hover:bg-hover/60', selected?.id === ticket.id ? 'bg-hover/70' : '')}>
                <Inbox className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-foreground">{ticket.subject}</span>
                    {ticket.unreadByAdmin ? <span className="shrink-0 text-xs font-medium text-cyan">{text.unread}</span> : null}
                  </span>
                  <span className="mt-1 block truncate text-xs text-secondary-text">{ticket.requesterEmail || `#${ticket.userId}`}</span>
                  <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-secondary-text">
                    <span>{statusLabel(ticket.status)}</span><span>#{ticket.id}</span><span>{formatTime(ticket.updatedAt, language)}</span>
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className="min-w-0">
          {!selected ? <p className="px-5 py-16 text-center text-sm text-secondary-text">{text.select}</p> : (
            <>
              <div className="flex flex-col gap-3 border-b border-border/70 px-5 py-4 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <h4 className="break-words text-base font-semibold text-foreground">#{selected.id} · {selected.subject}</h4>
                  <p className="mt-1 text-xs text-secondary-text">{selected.requesterEmail} · {statusLabel(selected.status)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn-ghost" onClick={() => void updateStatus('open')} disabled={busy || selected.status === 'open'}>{text.markOpen}</button>
                  <button type="button" className="btn-ghost" onClick={() => void updateStatus('in_progress')} disabled={busy || selected.status === 'in_progress'}>{text.markProgress}</button>
                  <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void updateStatus('closed')} disabled={busy || selected.status === 'closed'}>
                    <CheckCircle2 className="h-4 w-4" />{text.markClosed}
                  </button>
                </div>
              </div>
              <div className="max-h-[25rem] space-y-3 overflow-y-auto px-5 py-5">
                {selected.messages.map((message) => (
                  <div key={message.id} className={cn('max-w-[92%] rounded-lg border px-4 py-3', message.authorRole === 'admin' ? 'ml-auto border-cyan/25 bg-cyan/8' : 'border-border/70 bg-hover/45')}>
                    <div className="flex justify-between gap-3 text-xs text-secondary-text">
                      <span className="font-medium text-foreground">{message.authorRole === 'admin' ? text.admin : text.user}</span>
                      <span>{formatTime(message.createdAt, language)}</span>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap break-words text-sm text-foreground">{message.body}</p>
                  </div>
                ))}
              </div>
              <form className="space-y-3 border-t border-border/70 px-5 py-4" onSubmit={(event) => void sendReply(event)}>
                <label className="block text-sm font-medium text-foreground">
                  <span className="mb-1.5 block">{text.reply}</span>
                  <textarea className="input-base min-h-24 w-full resize-y" aria-label={text.reply} placeholder={text.replyPlaceholder} value={reply} onChange={(event) => setReply(event.target.value)} minLength={2} maxLength={4000} required disabled={selected.status === 'closed'} />
                </label>
                <button type="submit" className="btn-primary inline-flex items-center gap-2" disabled={busy || selected.status === 'closed'}>
                  <Send className="h-4 w-4" />{busy ? text.sending : text.send}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </Card>
  );
};

export default SupportWorkbenchV120;
