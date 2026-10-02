import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import DemoControls from './DemoControls'
import { apiClient } from '../config/api'

vi.mock('../config/api', () => ({
  apiClient: {
    getIncidents: vi.fn().mockResolvedValue({ items: [], next_token: null, count: 0 }),
    injectFault: vi.fn().mockResolvedValue({ data: { details: {}, message: 'ok' }, error: null }),
    approveIncidentMain: vi.fn().mockResolvedValue({ data: {}, error: null }),
  },
  configError: null
}))

describe('DemoControls', () => {
  it('renders without throwing', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <DemoControls />
      </MemoryRouter>
    )
    
    await waitFor(() => {
      expect(screen.getByText('Trigger a Fault')).toBeInTheDocument()
    })
    
    expect(screen.getByText('Break it')).toBeInTheDocument()
    expect(screen.getByText('Expose it')).toBeInTheDocument()
    expect(screen.getByText('Trigger cascade')).toBeInTheDocument()
  })
})
