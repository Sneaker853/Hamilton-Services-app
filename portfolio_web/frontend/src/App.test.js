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
  let consoleWarnSpy;
  let consoleErrorSpy;

  beforeAll(() => {
    consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterAll(() => {
    consoleWarnSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });

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

  test('shows a friendly service notice when the backend times out', async () => {
    localStorage.setItem('guestMode', 'true');
    axios.get.mockReset();
    axios.get.mockRejectedValueOnce({ code: 'ECONNABORTED', message: 'timeout exceeded' });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Live service notice/i)).toBeInTheDocument();
      expect(screen.getByText(/Please wait about 30–90 seconds/i)).toBeInTheDocument();
    });
  });
});
