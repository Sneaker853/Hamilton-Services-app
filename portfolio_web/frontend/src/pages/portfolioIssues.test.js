import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import Goals from './Goals';
import PortfolioComparison from './PortfolioComparison';
import StockComparison from './StockComparison';
import { LanguageProvider } from '../components';

jest.mock('axios', () => ({
  get: jest.fn(),
  post: jest.fn(),
  delete: jest.fn(),
  defaults: {},
  interceptors: {
    request: { use: jest.fn() },
    response: { use: jest.fn() },
  },
}));

const renderWithLanguage = (ui) => render(<LanguageProvider>{ui}</LanguageProvider>);

describe('portfolio issue regressions', () => {
  beforeEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
  });

  test('goals ticker search shows suggestions from the stocks search results payload', async () => {
    jest.useFakeTimers();

    axios.get.mockImplementation((url) => {
      if (url.includes('/goals')) {
        return Promise.resolve({ data: { goals: [] } });
      }
      if (url.includes('/portfolios')) {
        return Promise.resolve({ data: { portfolios: [] } });
      }
      if (url.includes('/stocks/search')) {
        return Promise.resolve({
          data: {
            results: [{ ticker: 'AAPL', name: 'Apple Inc.' }],
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    renderWithLanguage(<Goals apiBase="http://localhost:8000/api" />);

    fireEvent.click(await screen.findByRole('button', { name: /new goal/i }));
    fireEvent.change(screen.getByPlaceholderText(/ticker \(e\.g\. aapl\)/i), {
      target: { value: 'AA' },
    });

    await act(async () => {
      jest.advanceTimersByTime(350);
    });

    await waitFor(() => {
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    });

    jest.useRealTimers();
  });

  test('portfolio comparison surfaces actual current values for selected portfolios', async () => {
    localStorage.setItem('authUser', JSON.stringify({ id: 1 }));

    axios.get.mockImplementation((url) => {
      if (url.endsWith('/portfolios')) {
        return Promise.resolve({
          data: {
            portfolios: [
              {
                id: 1,
                name: 'Growth',
                source: 'optimizer',
                created_at: '2025-01-15T00:00:00Z',
                data: {
                  investment_amount: 10000,
                  holdings: [{ ticker: 'AAPL', weight: 100, value: 11000, sector: 'Tech' }],
                  summary: { expected_return: 12, volatility: 18 },
                  metrics: { sharpe_ratio: 1.1 },
                },
              },
              {
                id: 2,
                name: 'Income',
                source: 'manual',
                created_at: '2025-02-01T00:00:00Z',
                data: {
                  investment_amount: 8000,
                  holdings: [{ ticker: 'JNJ', weight: 100, value: 7800, sector: 'Health' }],
                  summary: { expected_return: 7, volatility: 10 },
                  metrics: { sharpe_ratio: 0.8 },
                },
              },
            ],
          },
        });
      }
      if (url.includes('/portfolio-performance/1')) {
        return Promise.resolve({ data: { current_actual_value: 12500, total_return_pct: 25 } });
      }
      if (url.includes('/portfolio-performance/2')) {
        return Promise.resolve({ data: { current_actual_value: 7600, total_return_pct: -5 } });
      }
      return Promise.resolve({ data: {} });
    });

    renderWithLanguage(<PortfolioComparison apiBase="http://localhost:8000/api" />);

    fireEvent.click(await screen.findByRole('button', { name: /growth/i }));
    fireEvent.click(screen.getByRole('button', { name: /income/i }));

    await waitFor(() => {
      expect(screen.getByText('Current Value')).toBeInTheDocument();
      expect(screen.getByText('$12,500')).toBeInTheDocument();
      expect(screen.getByText('$7,600')).toBeInTheDocument();
    });
  });

  test('stock comparison formats decimal-based financial ratios as readable percentages', async () => {
    axios.get.mockImplementation((url, config) => {
      if (url.includes('/stocks/search')) {
        return Promise.resolve({
          data: { results: [{ ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ', sector: 'Technology' }] },
        });
      }
      if (url.includes('/stocks/AAPL')) {
        return Promise.resolve({
          data: {
            ticker: 'AAPL',
            name: 'Apple Inc.',
            exchange: 'NASDAQ',
            sector: 'Technology',
            current_price: 190.25,
            market_cap: 2800000000000,
            pe_ratio: 31.2,
            roe: 0.215,
            beta: 1.12,
            dividend_yield: 0.0048,
            expected_return: 0.126,
            volatility: 0.238,
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    renderWithLanguage(<StockComparison apiBase="http://localhost:8000/api" />);

    fireEvent.change(screen.getByPlaceholderText(/search by ticker or company name/i), {
      target: { value: 'AAP' },
    });

    await waitFor(() => {
      expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /aapl/i }));

    axios.get.mockImplementation((url) => {
      if (url.includes('/stocks/MSFT')) {
        return Promise.resolve({
          data: {
            ticker: 'MSFT',
            name: 'Microsoft',
            exchange: 'NASDAQ',
            sector: 'Technology',
            current_price: 420.1,
            market_cap: 3100000000000,
            pe_ratio: 34.1,
            roe: 0.31,
            beta: 0.98,
            dividend_yield: 0.0072,
            expected_return: 0.101,
            volatility: 0.201,
          },
        });
      }
      if (url.includes('/stocks/search')) {
        return Promise.resolve({
          data: { results: [{ ticker: 'MSFT', name: 'Microsoft', exchange: 'NASDAQ', sector: 'Technology' }] },
        });
      }
      if (url.includes('/stocks/AAPL')) {
        return Promise.resolve({
          data: {
            ticker: 'AAPL',
            name: 'Apple Inc.',
            exchange: 'NASDAQ',
            sector: 'Technology',
            current_price: 190.25,
            market_cap: 2800000000000,
            pe_ratio: 31.2,
            roe: 0.215,
            beta: 1.12,
            dividend_yield: 0.0048,
            expected_return: 0.126,
            volatility: 0.238,
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    fireEvent.change(screen.getByPlaceholderText(/search by ticker or company name/i), {
      target: { value: 'MSF' },
    });

    await waitFor(() => {
      expect(screen.getByText('Microsoft')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /msft/i }));

    await waitFor(() => {
      expect(screen.getByText('+21.50%')).toBeInTheDocument();
      expect(screen.getByText('+0.48%')).toBeInTheDocument();
      expect(screen.getByText('+12.6%')).toBeInTheDocument();
      expect(screen.getByText('+23.8%')).toBeInTheDocument();
    });
  });
});
