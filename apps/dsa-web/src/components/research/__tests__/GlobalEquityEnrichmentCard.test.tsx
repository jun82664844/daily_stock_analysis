import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { GlobalEquityEnrichmentCard } from '../GlobalEquityEnrichmentCard';


const payload = {
  title: 'US equity public data expansion',
  summary: 'Direct public source data is available.',
  market: 'us' as const,
  status: 'available',
  source: 'global_equity_public_adapter',
  aiUsed: false,
  publicSearchUsed: false,
  channels: [
    {
      category: 'news',
      title: 'Company news',
      summary: 'One public headline is available.',
      status: 'available',
      source: 'yahoo_finance_search_feed',
      items: [
        {
          title: 'Apple publishes a product update',
          summary: 'Example News',
          publishedAt: '2026-07-11T00:00:00+00:00',
          url: 'https://finance.yahoo.com/news/apple-update',
          source: 'yahoo_finance_search_feed',
        },
      ],
      action: 'Open source.',
    },
    {
      category: 'filings',
      title: 'SEC filings',
      summary: 'Official SEC filings are available.',
      status: 'available',
      source: 'sec_edgar_submissions',
      items: [
        {
          title: '10-Q - Quarterly report',
          summary: 'Filed 2026-07-10; report date 2026-06-30.',
          documentType: '10-Q',
          url: 'https://www.sec.gov/example',
          source: 'sec_edgar_submissions',
        },
      ],
      action: 'Read filing.',
    },
    {
      category: 'fundamentals',
      title: 'Company facts',
      summary: 'Two normalized company facts are available.',
      status: 'available',
      source: 'yfinance_profile',
      items: [
        { label: 'Sector', value: 'Technology', source: 'yfinance_profile' },
        { label: 'Industry', value: 'Consumer Electronics', source: 'yfinance_profile' },
      ],
      action: 'Review facts.',
    },
  ],
  diagnostics: { cacheHit: false, elapsedMs: 120 },
  premiumUnlock: 'Configured APIs can add coverage.',
  boundary: 'Information and data only; not investment advice or a trading instruction.',
};


describe('GlobalEquityEnrichmentCard', () => {
  it('renders Chinese product chrome with source links and no-AI boundary', () => {
    render(<GlobalEquityEnrichmentCard payload={payload} language="zh" />);

    expect(screen.getByText('港美股公开数据')).toBeInTheDocument();
    expect(screen.getByText('公司资讯')).toBeInTheDocument();
    expect(screen.getByText('SEC 文件')).toBeInTheDocument();
    expect(screen.getByText('板块')).toBeInTheDocument();
    expect(screen.getByText('行业')).toBeInTheDocument();
    expect(screen.getByText('提交日期 2026-07-10；报告期 2026-06-30。')).toBeInTheDocument();
    expect(screen.queryByText('Sector')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Apple publishes a product update' })).toHaveAttribute(
      'href',
      'https://finance.yahoo.com/news/apple-update',
    );
    expect(screen.getByText('仅提供资讯和数据，不构成投资建议或交易指令。')).toBeInTheDocument();
  });

  it('renders English product chrome when English is selected', () => {
    render(<GlobalEquityEnrichmentCard payload={payload} language="en" />);

    expect(screen.getByText('US / HK public data')).toBeInTheDocument();
    expect(screen.getByText('Company news')).toBeInTheDocument();
    expect(screen.getByText('SEC filings')).toBeInTheDocument();
    expect(screen.getByText('Information and data only; not investment advice or a trading instruction.')).toBeInTheDocument();
  });
});
