import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import AssetSearchSection from './AssetSearchSection';

describe('AssetSearchSection', () => {
  const baseProps = {
    searchValue: '',
    onSearchChange: jest.fn(),
    assetFilter: 'all',
    onFilterChange: jest.fn(),
    marketFilter: 'all',
    onMarketChange: jest.fn(),
    marketOptions: ['NASDAQ'],
    financialSectorFilter: 'all',
    onFinancialSectorChange: jest.fn(),
    financialSectorOptions: ['Technology'],
    onSelect: jest.fn(),
    loading: false,
    selectedTickers: new Set(),
  };

  test('renders result rows as accessible buttons', () => {
    render(
      <AssetSearchSection
        {...baseProps}
        items={[{ ticker: 'AAPL', name: 'Apple Inc.' }]}
      />
    );

    const rowButton = screen.getByRole('button', { name: /Add AAPL/i });
    expect(rowButton).toBeInTheDocument();
  });

  test('calls onSelect when clicking result row button', () => {
    const onSelect = jest.fn();

    render(
      <AssetSearchSection
        {...baseProps}
        onSelect={onSelect}
        items={[{ ticker: 'MSFT', name: 'Microsoft Corp.' }]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Add MSFT/i }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith({ ticker: 'MSFT', name: 'Microsoft Corp.' });
  });

  test('shows empty-state message for no results', () => {
    render(
      <AssetSearchSection
        {...baseProps}
        items={[]}
      />
    );

    expect(screen.getByText(/No matching securities found/i)).toBeInTheDocument();
  });
});
