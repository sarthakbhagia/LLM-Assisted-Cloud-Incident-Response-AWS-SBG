import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { apiClient } from './config/api'

vi.mock('./config/api', () => ({
  apiClient: {
    getHealth: vi.fn().mockResolvedValue({
      overall: 'ok',
      region: 'ap-south-1',
      services: []
    }),
    getIncidents: vi.fn().mockResolvedValue({ items: [], next_token: null, count: 0 }),
    getAnalytics: vi.fn().mockResolvedValue({ kpis: { activeIncidents: 0, pendingApprovals: 0, recoverySuccessRate: 0, averageMTTR: 0 } })
  },
  configError: null
}))

describe('App', () => {
  it('renders without throwing', async () => {
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
