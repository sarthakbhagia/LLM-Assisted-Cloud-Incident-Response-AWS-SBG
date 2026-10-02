import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import IncidentDetail from './IncidentDetail';

vi.mock('../config/api.js', () => ({
  apiClient: {
    getIncidentDetail: vi.fn(),
    getIncidentEvidence: vi.fn(),
  },
}));

import { apiClient } from '../config/api.js';

describe('IncidentDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders old incident with alarm_thresholds object without crashing', async () => {
    apiClient.getIncidentDetail.mockResolvedValue({
      incident_id: '066fbb57-c95e-4f98-b20b-119a276ee0f4',
      fault_class: 'resource_exhaustion',
      detected_at: '2026-10-02T07:37:52.811743+00:00',
      diagnosis: {
        root_cause: 'Test root cause unique xyz',
        confidence: 0.95,
        suggested_action: 'scale_up',
        model_used: 'Nova Pro',
        explanation: 'Test explanation',
        reasoning_trace: 'Test trace',
        used_rag: true,
        failure_mode: null,
        is_heuristic: false,
      },
      remediation: { status: 'executed', action_taken: 'scale_up', executed_at: '2026-10-02T07:40:26.206048+00:00' },
      verification: { status: 'resolved', checked_at: '2026-10-02T07:42:31.758741+00:00' },
    });

    apiClient.getIncidentEvidence.mockResolvedValue({
      incident_id: '066fbb57-c95e-4f98-b20b-119a276ee0f4',
      fault_class: 'resource_exhaustion',
      s3_key: 'test',
      evidence: {
        evidence: {
          alarm_thresholds: {
            threshold: 50000,
            metric_name: 'Duration',
            comparison_operator: 'GreaterThanThreshold',
          },
          metrics: {
            duration: [{ timestamp: '2026-10-02T10:00:00Z', value: 45000 }],
          },
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/incidents/066fbb57-c95e-4f98-b20b-119a276ee0f4']}>
        <IncidentDetail />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test root cause unique xyz' })).toBeInTheDocument();
    });
  });

  it('renders new incident without alarm_thresholds without crashing', async () => {
    apiClient.getIncidentDetail.mockResolvedValue({
      incident_id: '536406ba-dc59-45d8-a1b4-daf604bdb201',
      fault_class: 'resource_exhaustion',
      detected_at: '2026-10-02T08:15:31.744460+00:00',
      diagnosis: {
        root_cause: 'Test root cause 2 unique abc',
        confidence: 0.85,
        suggested_action: 'scale_up',
        model_used: 'Nova Pro',
        explanation: 'Test explanation 2',
        reasoning_trace: 'Test trace 2',
        used_rag: true,
        failure_mode: null,
        is_heuristic: false,
      },
      remediation: { status: 'pending_approval' },
      verification: { status: 'not_run' },
    });

    apiClient.getIncidentEvidence.mockResolvedValue({
      incident_id: '536406ba-dc59-45d8-a1b4-daf604bdb201',
      fault_class: 'resource_exhaustion',
      s3_key: 'test',
      evidence: {
        evidence: {
          // No alarm_thresholds at all!
          metrics: {
            duration: [],
          },
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/incidents/536406ba-dc59-45d8-a1b4-daf604bdb201']}>
        <IncidentDetail />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test root cause 2 unique abc' })).toBeInTheDocument();
    });
  });

  it('renders incident with empty metrics without crashing', async () => {
    apiClient.getIncidentDetail.mockResolvedValue({
      incident_id: 'empty-metrics',
      fault_class: 'resource_exhaustion',
      detected_at: '2026-10-02T10:00:00.000Z',
      diagnosis: {
        root_cause: 'Test unique root cause empty',
        confidence: 0.5,
        suggested_action: 'scale_up',
        model_used: 'Nova Pro',
        explanation: 'Test',
        reasoning_trace: 'Test',
        used_rag: true,
      },
      remediation: { status: 'pending_approval' },
      verification: { status: 'not_run' },
    });

    apiClient.getIncidentEvidence.mockResolvedValue({
      incident_id: 'empty-metrics',
      fault_class: 'resource_exhaustion',
      s3_key: 'test',
      evidence: {
        evidence: {
          metrics: {}, // empty metrics
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/incidents/empty-metrics']}>
        <IncidentDetail />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test unique root cause empty' })).toBeInTheDocument();
    });
  });

  it('renders incident with error-shaped evidence response', async () => {
    apiClient.getIncidentDetail.mockResolvedValue({
      incident_id: 'error-evidence',
      fault_class: 'resource_exhaustion',
      detected_at: '2026-10-02T10:00:00.000Z',
      diagnosis: { root_cause: 'Test unique error case', confidence: 0.5, suggested_action: 'scale_up' },
      remediation: { status: 'pending_approval' },
      verification: { status: 'not_run' },
    });

    apiClient.getIncidentEvidence.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter initialEntries={['/incidents/error-evidence']}>
        <IncidentDetail />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test unique error case' })).toBeInTheDocument();
    });
  });
});