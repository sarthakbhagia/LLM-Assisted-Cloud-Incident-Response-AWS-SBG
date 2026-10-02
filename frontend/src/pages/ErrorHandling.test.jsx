import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { apiClient } from '../config/api'

describe('Error Handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('handles API returning HTML instead of JSON', async () => {
    // Mock fetch to return HTML (simulating a 404 page or proxy error)
    vi.mock('../config/api', () => ({
      apiClient: {
        getHealth: vi.fn().mockRejectedValue(new Error('HTTP error! status: 404')),
        getIncidents: vi.fn().mockRejectedValue(new Error('HTTP error! status: 404')),
        getAnalytics: vi.fn().mockRejectedValue(new Error('HTTP error! status: 404')),
      },
      configError: null
    }))

    const { apiClient: mockedClient } = await import('../config/api')
    
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    )
    
    // Should not throw - the error boundary should catch it
    await waitFor(() => {
      expect(screen.getByText('Incident Command')).toBeInTheDocument()
    })
  })

  it('handles 500 response from API', async () => {
    vi.mock('../config/api', () => ({
      apiClient: {
        getHealth: vi.fn().mockRejectedValue(new Error('HTTP error! status: 500')),
        getIncidents: vi.fn().mockRejectedValue(new Error('HTTP error! status: 500')),
        getAnalytics: vi.fn().mockRejectedValue(new Error('HTTP error! status: 500')),
      },
      configError: null
    }))

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    )
    
    await waitFor(() => {
      expect(screen.getByText('Incident Command')).toBeInTheDocument()
    })
  })

  it('handles network rejection', async () => {
    vi.mock('../config/api', () => ({
      apiClient: {
        getHealth: vi.fn().mockRejectedValue(new Error('Failed to fetch')),
        getIncidents: vi.fn().mockRejectedValue(new Error('Failed to fetch')),
        getAnalytics: vi.fn().mockRejectedValue(new Error('Failed to fetch')),
      },
      configError: null
    }))

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    )
    
    await waitFor(() => {
      expect(screen.getByText('Incident Command')).toBeInTheDocument()
    })
  })
})
