import { describe, it, expect } from 'vitest'

// This test verifies that all named imports from utils/constants 
// are actually exported from the module

import * as constants from './constants'

describe('utils/constants exports', () => {
  const expectedExports = [
    'FAULT_CLASSES',
    'FAULT_CLASS_LABELS',
    'FAULT_CLASS_DESCRIPTIONS',
    'FAULT_CLASS_SEVERITY',
    'FAULT_CLASS_ICONS',
    'REMEDIATION_STATUSES',
    'VERIFICATION_STATUSES',
    'PIPELINE_STAGES',
    'PIPELINE_STAGE_DETAILS',
    'CONFIDENCE_LEVELS',
    'SEVERITY_LEVELS',
    'ACTION_RISK',
    'ACTION_LABELS',
    'HIGH_RISK_ACTIONS',
    'POLLING_INTERVALS',
    'DATE_FORMATS',
    'DEMO_ACTION_LABELS',
    'SPEED_OPTIONS',
    'CHART_COLORS',
    'STATUS_ICONS',
    'getConfidenceLevel',
    // Functions
  ]

  it('exports all expected constants', () => {
    for (const name of expectedExports) {
      expect(name in constants).toBe(true)
    }
  })
})
