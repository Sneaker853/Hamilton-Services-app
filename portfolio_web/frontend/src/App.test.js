import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';

jest.mock('axios', () => ({
  get: jest.fn(),
  post: jest.fn(),
  defaults: {},
  interceptors: {
    request: { use: jest.fn() },
    response: { use: jest.fn() },
  },
}));

import App from './App';

describe('App smoke tests', () => {
  beforeEach(() => {
    localStorage.clear();
    axios.get.mockResolvedValue({ data: {} });
    axios.post.mockResolvedValue({ data: {} });
  });

  test('shows login screen when unauthenticated', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Sign In')).toBeInTheDocument();
    });
  });

  test('shows app shell in guest mode', async () => {
    localStorage.setItem('guestMode', 'true');

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    });
  });
});
