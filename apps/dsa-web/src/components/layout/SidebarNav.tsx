import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, BarChart3, Bell, BookOpenText, BriefcaseBusiness, Gauge, Globe2, Home, LifeBuoy, LogOut, MessageSquareQuote, Search, Settings2, ShieldCheck, UserRound } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { PLATFORM_SESSION_CHANGED_EVENT, platformApi } from '../../api/platform';
import { SUPPORT_INBOX_CHANGED_EVENT, supportApi } from '../../api/support';
import { useAuth } from '../../contexts/AuthContext';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiTextKey } from '../../i18n/uiText';
import { cn } from '../../utils/cn';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { StatusDot } from '../common/StatusDot';
import { UiLanguageToggle } from '../i18n/UiLanguageToggle';
import { ThemeToggle } from '../theme/ThemeToggle';

type SidebarNavProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
  variant?: 'default' | 'rail';
};

type NavItem = {
  key: string;
  labelKey: UiTextKey;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  badge?: 'completion';
};

const NAV_ITEMS: NavItem[] = [
  { key: 'home', labelKey: 'layout.nav.home', to: '/', icon: Home, exact: true },
  { key: 'chat', labelKey: 'layout.nav.chat', to: '/chat', icon: MessageSquareQuote, badge: 'completion' },
  { key: 'market', labelKey: 'layout.nav.market', to: '/market', icon: Globe2 },
  { key: 'screening', labelKey: 'layout.nav.screening', to: '/screening', icon: Search },
  { key: 'research', labelKey: 'layout.nav.research', to: '/research', icon: BookOpenText },
  { key: 'portfolio', labelKey: 'layout.nav.portfolio', to: '/portfolio', icon: BriefcaseBusiness },
  { key: 'decision-signals', labelKey: 'layout.nav.decisionSignals', to: '/decision-signals', icon: Activity },
  { key: 'backtest', labelKey: 'layout.nav.backtest', to: '/backtest', icon: BarChart3 },
  { key: 'alerts', labelKey: 'layout.nav.alerts', to: '/alerts', icon: Bell },
  { key: 'usage', labelKey: 'layout.nav.usage', to: '/usage', icon: Gauge },
  { key: 'account', labelKey: 'layout.nav.account', to: '/account', icon: UserRound },
  { key: 'support', labelKey: 'layout.nav.support', to: '/support', icon: LifeBuoy },
  { key: 'admin', labelKey: 'layout.nav.admin', to: '/admin', icon: ShieldCheck },
  { key: 'settings', labelKey: 'layout.nav.settings', to: '/settings', icon: Settings2 },
];

export const SidebarNav: React.FC<SidebarNavProps> = ({ collapsed = false, onNavigate, variant = 'default' }) => {
  const { authEnabled, loggedIn, logout } = useAuth();
  const { language, t } = useUiLanguage();
  const completionBadge = useAgentChatStore((state) => state.completionBadge);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [platformRole, setPlatformRole] = useState<string | null>('loading');
  const [supportUnread, setSupportUnread] = useState(0);
  const [adminPending, setAdminPending] = useState(0);
  const supportRequestId = useRef(0);

  const refreshSupportState = useCallback(async () => {
    const requestId = ++supportRequestId.current;

    try {
      const payload = await platformApi.current();
      if (requestId !== supportRequestId.current) return;

      const role = payload?.user?.role ?? null;
      const hasPlatformUser = Boolean(payload?.user?.id);
      const canReadAdmin = role === 'admin' || (loggedIn && role !== 'user');
      setPlatformRole(role);

      if (hasPlatformUser) {
        const userSummary = await supportApi.getSummary().catch(() => null);
        if (requestId !== supportRequestId.current) return;
        if (userSummary) setSupportUnread(userSummary.unreadCount);
      } else {
        setSupportUnread(0);
      }

      if (!canReadAdmin) {
        setAdminPending(0);
        return;
      }

      const adminSummary = await supportApi.adminGetSummary().catch(() => null);
      if (requestId !== supportRequestId.current) return;
      if (adminSummary) setAdminPending(adminSummary.pendingCount);
    } catch {
      if (requestId === supportRequestId.current) {
        setPlatformRole(null);
        setSupportUnread(0);
        setAdminPending(0);
      }
    }
  }, [loggedIn]);

  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') {
        void refreshSupportState();
      }
    };
    const initialRefreshId = window.setTimeout(() => void refreshSupportState(), 0);
    const intervalId = window.setInterval(refreshWhenVisible, 60_000);

    window.addEventListener(PLATFORM_SESSION_CHANGED_EVENT, refreshSupportState);
    window.addEventListener(SUPPORT_INBOX_CHANGED_EVENT, refreshSupportState);
    document.addEventListener('visibilitychange', refreshWhenVisible);

    return () => {
      supportRequestId.current += 1;
      window.clearTimeout(initialRefreshId);
      window.clearInterval(intervalId);
      window.removeEventListener(PLATFORM_SESSION_CHANGED_EVENT, refreshSupportState);
      window.removeEventListener(SUPPORT_INBOX_CHANGED_EVENT, refreshSupportState);
      document.removeEventListener('visibilitychange', refreshWhenVisible);
    };
  }, [refreshSupportState]);

  const showAdminOnlyNav = platformRole === 'admin' || (loggedIn && platformRole !== 'user');
  const navItems = NAV_ITEMS.filter((item) => !['admin', 'settings'].includes(item.key) || showAdminOnlyNav);
  const isRail = variant === 'rail';
  const itemBaseClass = cn(
    'group relative flex h-[var(--nav-item-height)] w-full items-center overflow-hidden rounded-2xl border border-transparent text-sm leading-none text-secondary-text transition-all',
    isRail
      ? 'justify-center gap-2.5 px-2'
      : collapsed
        ? 'justify-center px-0'
        : 'gap-3 px-[var(--nav-item-padding-x)]'
  );
  const itemInteractiveClass = cn(
    itemBaseClass,
    'hover:bg-[var(--nav-hover-bg)] hover:text-foreground'
  );
  const itemActiveClass = 'border-[var(--nav-active-border)] bg-[var(--nav-active-bg)] font-medium text-[hsl(var(--primary))]';
  const itemIconClass = cn(isRail ? 'h-[18px] w-[18px]' : 'h-5 w-5', 'shrink-0');
  const itemLabelClass = cn('truncate', isRail ? 'text-center' : '');

  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          'flex items-center',
          isRail ? 'mb-5 justify-center gap-2 pt-1' : 'mb-4 gap-2 px-1',
          collapsed || isRail ? 'justify-center' : ''
        )}
      >
        <div
          className={cn(
            'flex items-center justify-center bg-primary-gradient text-[hsl(var(--primary-foreground))] shadow-[0_12px_28px_var(--nav-brand-shadow)]',
            isRail ? 'h-9 w-9 rounded-[1rem]' : 'h-10 w-10 rounded-2xl'
          )}
        >
          <BarChart3 className={cn(isRail ? 'h-[19px] w-[19px]' : 'h-5 w-5')} />
        </div>
        {!collapsed ? (
          <p className={cn('min-w-0 truncate font-semibold text-foreground', isRail ? 'text-[0.95rem] leading-none' : 'text-sm')}>DSA</p>
        ) : null}
      </div>

      <nav className={cn('flex flex-col gap-1.5', isRail ? '' : 'flex-1')} aria-label={t('layout.mainNav')}>
        {navItems.map(({ key, labelKey, to, icon: Icon, exact, badge }) => {
          const label = t(labelKey);
          const badgeCount = key === 'support' ? supportUnread : key === 'admin' ? adminPending : 0;
          const badgeText = badgeCount > 99 ? '99+' : String(badgeCount);
          const ariaLabel = key === 'support' && badgeCount > 0
            ? language === 'en' ? `${label}, ${badgeCount} unread replies` : `${label}，${badgeCount} 条新回复`
            : key === 'admin' && badgeCount > 0
              ? language === 'en' ? `${label}, ${badgeCount} pending support tickets` : `${label}，${badgeCount} 张待处理客服工单`
              : label;
          return (
          <NavLink
            key={key}
            to={to}
            end={exact}
            onClick={onNavigate}
            aria-label={ariaLabel}
            className={({ isActive }) =>
              cn(
                itemInteractiveClass,
                isActive ? itemActiveClass : ''
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn(itemIconClass, isActive ? 'text-[var(--nav-icon-active)]' : 'text-current')} />
                {!collapsed ? <span className={itemLabelClass}>{label}</span> : null}
                {badge === 'completion' && completionBadge ? (
                  <StatusDot
                    tone="info"
                    data-testid="chat-completion-badge"
                    className={cn(
                      'absolute right-3 border-2 border-background shadow-[0_0_10px_var(--nav-indicator-shadow)]',
                      collapsed ? 'right-2 top-2' : ''
                    )}
                    aria-label={t('layout.newChatMessage')}
                  />
                ) : null}
                {badgeCount > 0 ? (
                  <span
                    data-testid={key === 'support' ? 'support-user-badge' : 'support-admin-badge'}
                    aria-hidden="true"
                    className={cn(
                      'absolute right-3 flex h-5 min-w-5 items-center justify-center rounded-full bg-[hsl(var(--primary))] px-1 text-[10px] font-semibold text-[hsl(var(--primary-foreground))]',
                      collapsed ? 'right-1 top-1' : ''
                    )}
                  >
                    {badgeText}
                  </span>
                ) : null}
              </>
            )}
          </NavLink>
        );
        })}

        <ThemeToggle
          variant={isRail ? 'rail' : 'nav'}
          collapsed={collapsed}
          wrapperClassName="w-full"
          triggerClassName={itemInteractiveClass}
          triggerActiveClassName={itemActiveClass}
          iconClassName={itemIconClass}
          labelClassName={itemLabelClass}
        />
        <UiLanguageToggle
          variant={isRail ? 'rail' : 'nav'}
          collapsed={collapsed}
          wrapperClassName="w-full"
          triggerClassName={itemInteractiveClass}
          triggerActiveClassName={itemActiveClass}
          iconClassName={itemIconClass}
          labelClassName={itemLabelClass}
        />
      </nav>

      {authEnabled && loggedIn ? (
        <button
          type="button"
          onClick={() => setShowLogoutConfirm(true)}
          className={cn(
            itemInteractiveClass,
            isRail ? 'mt-1.5' : 'mt-5'
          )}
        >
          <LogOut className={itemIconClass} />
          {!collapsed ? <span className={itemLabelClass}>{t('layout.logout')}</span> : null}
        </button>
      ) : null}

      <ConfirmDialog
        isOpen={showLogoutConfirm}
        title={t('layout.logoutTitle')}
        message={t('layout.logoutMessage')}
        confirmText={t('layout.logoutConfirm')}
        cancelText={t('common.cancel')}
        isDanger
        onConfirm={() => {
          setShowLogoutConfirm(false);
          onNavigate?.();
          void logout();
        }}
        onCancel={() => setShowLogoutConfirm(false)}
      />
    </div>
  );
};
