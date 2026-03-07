import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import HoldingsTable from './HoldingsTable';

describe('HoldingsTable keyboard-friendly reorder controls', () => {
  const holdings = [
    { ticker: 'AAPL', sector: 'Technology', weight: 50, value: 50000, shares: 120, expected_return: 10, volatility: 20, return_estimator: 'ff5_blend' },
    { ticker: 'MSFT', sector: 'Technology', weight: 50, value: 50000, shares: 80, expected_return: 9, volatility: 18, return_estimator: 'capm' },
  ];

  test('renders move up/down controls and fires handlers', () => {
    const onMoveUp = jest.fn();
    const onMoveDown = jest.fn();

    render(
      <HoldingsTable
        holdings={holdings}
        onWeightChange={jest.fn()}
        onRemove={jest.fn()}
        onDragStart={jest.fn()}
        onDrop={jest.fn()}
        onDragEnd={jest.fn()}
        onMoveUp={onMoveUp}
        onMoveDown={onMoveDown}
      />
    );

    const upButton = screen.getByRole('button', { name: /Move MSFT up/i });
    const downButton = screen.getByRole('button', { name: /Move AAPL down/i });

    fireEvent.click(upButton);
    fireEvent.click(downButton);

    expect(onMoveUp).toHaveBeenCalledWith('MSFT');
    expect(onMoveDown).toHaveBeenCalledWith('AAPL');
  });
});
