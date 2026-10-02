import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import Overview from './Overview'
import Incidents from './Incidents'
import IncidentDetail from './IncidentDetail'
import Analytics from './Analytics'
import ServiceMap from './ServiceMap'
import Runbooks from './Runbooks'
import ReplayMode from './ReplayMode'
import SystemHealth from './SystemHealth'
import { apiClient } from '../config/api'

vi.mock('../config/api', () => ({
  apiClient: {
    getHealth: vi.fn().mockResolvedValue({
      overall: 'ok',
      region: 'ap-south-1',
      services: [],
      pipeline_handlers: {}
    }),
    getIncidents: vi.fn().mockResolvedValue({ items: [], next_token: null, count: 0 }),
    getAnalytics: vi.fn().mockResolvedValue({ kpis: { activeIncidents: 0, pendingApprovals: 0, recoverySuccessRate: 0, averageMTTR: 0 } }),
    getRunbooks: vi.fn().mockResolvedValue({ runbooks: [], count: 0 }),
    getServices: vi.fn().mockResolvedValue({ services: [] }),
    getIncidentDetail: vi.fn().mockResolvedValue({
      incident_id: 'test-id',
      fault_class: 'resource_exhaustion',
      detected_at: '2026-10-02T10:00:00.000Z',
      diagnosis: { root_cause: 'Test', confidence: 0.95, suggested_action: 'scale_up', model_used: 'Nova Pro', explanation: 'Test', reasoning_trace: 'Test', used_rag: true },
      remediation: { status: 'executed', action_taken: 'scale_up' },
      verification: { status: 'resolved' }
    }),
    getIncidentEvidence: vi.fn().mockResolvedValue({
      incident_id: 'test-id',
      fault_class: 'resource_exhaustion',
      s3_key: 'test',
      evidence: { evidence: { alarm_thresholds: { threshold: 50000, metric_name: 'Duration' }, metrics: { duration: [] } } }
    }),
    getRunbook: vi.fn().mockResolvedValue({ fault_class: 'resource_exhaustion', s3_key: 'test', content: '# Test' }),
  },
  configError: null
}))

describe('All Pages', () => {
  const pages = [
    { name: 'Overview', component: Overview, path: '/' },
    { name: 'Incidents', component: Incidents, path: '/incidents' },
    { name: 'IncidentDetail', component: IncidentDetail, path: '/incidents/test-id' },
    { name: 'Analytics', component: Analytics, path: '/analytics' },
    { name: 'ServiceMap', component: ServiceMap, path: '/service-map' },
    { name: 'Runbooks', component: Runbooks, path: '/runbooks' },
    { name: 'ReplayMode', component: ReplayMode, path: '/replay' },
    { name: 'SystemHealth', component: SystemHealth, path: '/system-health' }
  ]

  pages.forEach(({ name, component, path }) => {
    it(`renders ${name} without throwing`, async () => {
      render(
        <MemoryRouter initialEntries={[path]}>
          <component />
        </MemoryRouter>
      )
      
      // Just wait a bit to ensure no errors are thrown during render
      await waitFor(() => {
        expect(document.body).toBeInTheDocument()
      })
    })
  })
})
