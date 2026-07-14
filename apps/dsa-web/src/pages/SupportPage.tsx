import { useCallback, useEffect, useMemo, useState } from 'react';
import { LifeBuoy, RefreshCw, Send, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { platformApi } from '../api/platform';
import {
  supportApi,
  type SupportCategory,
  type SupportTicketDetail,
  type SupportTicketSummary,
} from '../api/support';
import { AppPage, Card, InlineAlert, PageHeader } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { cn } from '../utils/cn';

const TEXT = {
  zh: {
    eyebrow: '客户支持',
    title: '客服中心',
    description: '账户、行情数据、模型、报告和产品故障由人工客服处理；客服回复仅提供产品支持，不构成投资建议。',
    loginTitle: '登录后联系客服',
    loginDescription: '客服工单与平台账户隔离保存，需要先登录 DSA 平台账户。',
    loginAction: '前往登录',
    createTitle: '提交新工单',
    category: '问题分类',
    subject: '问题主题',
    subjectPlaceholder: '简要描述问题',
    message: '问题描述',
    messagePlaceholder: '请提供复现现象、页面或数据时间，不要填写密码或 API Key。',
    submit: '提交工单',
    submitting: '提交中',
    ticketsTitle: '我的工单',
    emptyTickets: '暂无工单。',
    refresh: '刷新',
    threadTitle: '工单详情',
    selectTicket: '选择一张工单查看对话。',
    reply: '追加消息',
    send: '发送消息',
    sending: '发送中',
    close: '关闭工单',
    closing: '关闭中',
    closedNotice: '该工单已关闭。如有新问题，请提交新工单。',
    user: '我',
    admin: '客服',
    unread: '新回复',
    loadError: '客服数据加载失败',
    actionError: '客服操作失败',
  },
  en: {
    eyebrow: 'Customer support',
    title: 'Support center',
    description: 'Human support handles accounts, market data, models, reports, and product issues. Product support is not investment advice.',
    loginTitle: 'Sign in to contact support',
    loginDescription: 'Support tickets are isolated by platform account. Sign in to your DSA account first.',
    loginAction: 'Go to sign in',
    createTitle: 'Create a ticket',
    category: 'Category',
    subject: 'Subject',
    subjectPlaceholder: 'Summarize the issue',
    message: 'Description',
    messagePlaceholder: 'Include the page, symptom, and data time. Never include passwords or API keys.',
    submit: 'Submit ticket',
    submitting: 'Submitting',
    ticketsTitle: 'My tickets',
    emptyTickets: 'No tickets yet.',
    refresh: 'Refresh',
    threadTitle: 'Ticket details',
    selectTicket: 'Select a ticket to view its conversation.',
    reply: 'Add message',
    send: 'Send message',
    sending: 'Sending',
    close: 'Close ticket',
    closing: 'Closing',
    closedNotice: 'This ticket is closed. Create a new ticket for a new issue.',
    user: 'Me',
    admin: 'Support',
    unread: 'New reply',
    loadError: 'Failed to load support data',
    actionError: 'Support action failed',
  },
} as const;

const CATEGORIES: SupportCategory[] = ['account', 'market_data', 'model', 'report', 'alerts', 'subscription', 'bug', 'other'];

const CATEGORY_LABELS: Record<'zh' | 'en', Record<SupportCategory, string>> = {
  zh: { account: '账户', market_data: '行情数据', model: '模型', report: '报告', alerts: '提醒', subscription: '订阅', bug: '产品故障', other: '其他' },
  en: { account: 'Account', market_data: 'Market data', model: 'Model', report: 'Report', alerts: 'Alerts', subscription: 'Subscription', bug: 'Product issue', other: 'Other' },
};

const STATUS_LABELS = {
  zh: { open: '待处理', in_progress: '处理中', closed: '已关闭' },
  en: { open: 'Open', in_progress: 'In progress', closed: 'Closed' },
} as const;

function errorText(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'parsedError' in error) {
    const parsed = (error as { parsedError?: { message?: string } }).parsedError;
    if (parsed?.message) return parsed.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function withoutMessages(ticket: SupportTicketDetail): SupportTicketSummary {
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

const SupportPage = () => {
  const { language } = useUiLanguage();
  const text = TEXT[language];
  const [accountState, setAccountState] = useState<'loading' | 'guest' | 'ready'>('loading');
  const [tickets, setTickets] = useState<SupportTicketSummary[]>([]);
  const [selected, setSelected] = useState<SupportTicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<SupportCategory>('other');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [reply, setReply] = useState('');
  const [busy, setBusy] = useState<'create' | 'reply' | 'close' | null>(null);

  const upsertTicket = useCallback((ticket: SupportTicketDetail) => {
    const summary = withoutMessages(ticket);
    setTickets((current) => [summary, ...current.filter((item) => item.id !== ticket.id)]);
  }, []);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await supportApi.listTickets();
      setTickets(response.tickets);
    } catch (nextError) {
      setError(errorText(nextError, text.loadError));
    } finally {
      setLoading(false);
    }
  }, [text.loadError]);

  useEffect(() => {
    let active = true;
    const start = async () => {
      try {
        const current = await platformApi.current();
        if (!active) return;
        if (!current?.user) {
          setAccountState('guest');
          setLoading(false);
          return;
        }
        setAccountState('ready');
        await loadTickets();
      } catch {
        if (active) {
          setAccountState('guest');
          setLoading(false);
        }
      }
    };
    void start();
    return () => { active = false; };
  }, [loadTickets]);

  const createTicket = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy('create');
    setError(null);
    try {
      const ticket = await supportApi.createTicket({ category, subject: subject.trim(), message: message.trim() });
      upsertTicket(ticket);
      setSelected(ticket);
      setSubject('');
      setMessage('');
      setCategory('other');
    } catch (nextError) {
      setError(errorText(nextError, text.actionError));
    } finally {
      setBusy(null);
    }
  };

  const openTicket = async (ticketId: number) => {
    setError(null);
    try {
      const ticket = await supportApi.getTicket(ticketId);
      setSelected(ticket);
      upsertTicket(ticket);
    } catch (nextError) {
      setError(errorText(nextError, text.loadError));
    }
  };

  const sendReply = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    setBusy('reply');
    setError(null);
    try {
      const ticket = await supportApi.addMessage(selected.id, reply.trim());
      setSelected(ticket);
      upsertTicket(ticket);
      setReply('');
    } catch (nextError) {
      setError(errorText(nextError, text.actionError));
    } finally {
      setBusy(null);
    }
  };

  const closeTicket = async () => {
    if (!selected) return;
    setBusy('close');
    setError(null);
    try {
      const ticket = await supportApi.closeTicket(selected.id);
      setSelected(ticket);
      upsertTicket(ticket);
    } catch (nextError) {
      setError(errorText(nextError, text.actionError));
    } finally {
      setBusy(null);
    }
  };

  const categoryOptions = useMemo(() => CATEGORY_LABELS[language], [language]);

  return (
    <AppPage>
      <div className="space-y-5">
        <PageHeader eyebrow={text.eyebrow} title={text.title} description={text.description} />
        {accountState === 'loading' ? <div className="h-48 animate-pulse rounded-lg bg-hover/50" /> : null}
        {accountState === 'guest' ? (
          <Card className="rounded-lg">
            <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground">{text.loginTitle}</h2>
                <p className="mt-1 text-sm text-secondary-text">{text.loginDescription}</p>
              </div>
              <Link to="/" className="btn-primary">{text.loginAction}</Link>
            </div>
          </Card>
        ) : null}
        {accountState === 'ready' ? (
          <>
            {error ? <InlineAlert variant="danger" message={error} /> : null}
            <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
              <div className="min-w-0 space-y-5">
                <Card title={text.createTitle} className="rounded-lg">
                  <form className="space-y-4" onSubmit={(event) => void createTicket(event)}>
                    <label className="block text-sm text-secondary-text">
                      <span className="mb-1.5 block font-medium text-foreground">{text.category}</span>
                      <select className="input-base w-full" value={category} onChange={(event) => setCategory(event.target.value as SupportCategory)} aria-label={text.category}>
                        {CATEGORIES.map((item) => <option key={item} value={item}>{categoryOptions[item]}</option>)}
                      </select>
                    </label>
                    <label className="block text-sm text-secondary-text">
                      <span className="mb-1.5 block font-medium text-foreground">{text.subject}</span>
                      <input className="input-base w-full" value={subject} onChange={(event) => setSubject(event.target.value)} placeholder={text.subjectPlaceholder} minLength={4} maxLength={120} required aria-label={text.subject} />
                    </label>
                    <label className="block text-sm text-secondary-text">
                      <span className="mb-1.5 block font-medium text-foreground">{text.message}</span>
                      <textarea className="input-base min-h-28 w-full resize-y" value={message} onChange={(event) => setMessage(event.target.value)} placeholder={text.messagePlaceholder} minLength={2} maxLength={4000} required aria-label={text.message} />
                    </label>
                    <button type="submit" className="btn-primary inline-flex items-center gap-2" disabled={busy !== null}>
                      <Send className="h-4 w-4" />
                      {busy === 'create' ? text.submitting : text.submit}
                    </button>
                  </form>
                </Card>

                <Card className="rounded-lg" padding="none">
                  <div className="flex items-center justify-between border-b border-border/70 px-5 py-4">
                    <h2 className="text-lg font-semibold text-foreground">{text.ticketsTitle}</h2>
                    <button type="button" className="btn-ghost inline-flex items-center gap-2" onClick={() => void loadTickets()} disabled={loading}>
                      <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />{text.refresh}
                    </button>
                  </div>
                  <div className="max-h-[30rem] divide-y divide-border/60 overflow-y-auto">
                    {!loading && tickets.length === 0 ? <p className="px-5 py-8 text-center text-sm text-secondary-text">{text.emptyTickets}</p> : null}
                    {tickets.map((ticket) => (
                      <button key={ticket.id} type="button" onClick={() => void openTicket(ticket.id)} className={cn('flex w-full min-w-0 items-start gap-3 px-5 py-4 text-left transition-colors hover:bg-hover/60', selected?.id === ticket.id ? 'bg-hover/70' : '')}>
                        <LifeBuoy className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
                        <span className="min-w-0 flex-1">
                          <span className="flex min-w-0 items-center justify-between gap-2">
                            <span className="truncate text-sm font-medium text-foreground">{ticket.subject}</span>
                            {ticket.unreadByUser ? <span className="shrink-0 text-xs font-medium text-cyan">{text.unread}</span> : null}
                          </span>
                          <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-secondary-text">
                            <span>{STATUS_LABELS[language][ticket.status]}</span>
                            <span>{categoryOptions[ticket.category]}</span>
                            <span>{formatTime(ticket.updatedAt, language)}</span>
                          </span>
                        </span>
                      </button>
                    ))}
                  </div>
                </Card>
              </div>

              <Card className="min-w-0 rounded-lg" padding="none">
                <div className="border-b border-border/70 px-5 py-4">
                  <h2 className="text-lg font-semibold text-foreground">{text.threadTitle}</h2>
                  {selected ? <p className="mt-1 break-words text-sm text-secondary-text">#{selected.id} · {selected.subject}</p> : null}
                </div>
                {!selected ? <p className="px-5 py-16 text-center text-sm text-secondary-text">{text.selectTicket}</p> : (
                  <div className="min-w-0">
                    <div className="max-h-[35rem] space-y-3 overflow-y-auto px-5 py-5">
                      {selected.messages.map((item) => (
                        <div key={item.id} className={cn('max-w-[92%] rounded-lg border px-4 py-3', item.authorRole === 'user' ? 'ml-auto border-cyan/25 bg-cyan/8' : 'border-border/70 bg-hover/45')}>
                          <div className="flex items-center justify-between gap-3 text-xs text-secondary-text">
                            <span className="font-medium text-foreground">{item.authorRole === 'user' ? text.user : text.admin}</span>
                            <span>{formatTime(item.createdAt, language)}</span>
                          </div>
                          <p className="mt-2 whitespace-pre-wrap break-words text-sm text-foreground">{item.body}</p>
                        </div>
                      ))}
                    </div>
                    <div className="border-t border-border/70 px-5 py-4">
                      {selected.status === 'closed' ? <InlineAlert variant="info" message={text.closedNotice} /> : (
                        <form className="space-y-3" onSubmit={(event) => void sendReply(event)}>
                          <label className="block text-sm font-medium text-foreground">
                            <span className="mb-1.5 block">{text.reply}</span>
                            <textarea className="input-base min-h-24 w-full resize-y" value={reply} onChange={(event) => setReply(event.target.value)} minLength={2} maxLength={4000} required aria-label={text.reply} />
                          </label>
                          <div className="flex flex-wrap gap-2">
                            <button type="submit" className="btn-primary inline-flex items-center gap-2" disabled={busy !== null}>
                              <Send className="h-4 w-4" />{busy === 'reply' ? text.sending : text.send}
                            </button>
                            <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void closeTicket()} disabled={busy !== null}>
                              <XCircle className="h-4 w-4" />{busy === 'close' ? text.closing : text.close}
                            </button>
                          </div>
                        </form>
                      )}
                    </div>
                  </div>
                )}
              </Card>
            </div>
          </>
        ) : null}
      </div>
    </AppPage>
  );
};

export default SupportPage;
