// API Configuration
// In local dev: leave VITE_API_BASE_URL unset. The Vite dev server proxy
// (vite.config.js server.proxy) routes /api/* to localhost:3001 automatically.
// In production: set VITE_API_BASE_URL to your API Gateway Prod stage URL, e.g.:
//   VITE_API_BASE_URL=https://<api-id>.execute-api.<region>.amazonaws.com/Prod
//   VITE_DEMO_API_BASE_URL=https://<demo-api-id>.execute-api.<region>.amazonaws.com/Prod
// Local dev: leave VITE_API_BASE_URL unset. Empty string means relative URLs,
// which Vite's dev server proxy routes to localhost:3001 (see vite.config.js).
// Production: VITE_API_BASE_URL must end at /Prod with NO trailing /api.
//   Correct:   VITE_API_BASE_URL=https://<id>.execute-api.<region>.amazonaws.com/Prod
//   Wrong:     VITE_API_BASE_URL=https://<id>.execute-api.<region>.amazonaws.com/Prod/api
// The frontend appends /api/incidents, /api/analytics etc. internally, so including
// /api in the base URL causes all evidence requests to hit /Prod/api/api/... (404).
//
// IMPORTANT: In production builds, VITE_API_BASE_URL and VITE_DEMO_API_BASE_URL MUST be set.
// If empty in production mode, a config error screen will be shown.


const isProduction = import.meta.env.PROD
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
const demoApiBaseUrl = import.meta.env.VITE_DEMO_API_BASE_URL

if (isProduction && (!apiBaseUrl || !demoApiBaseUrl)) {
  // This will be caught by the ConfigError boundary in main.jsx
  console.error('[Config] Missing required VITE_API_BASE_URL or VITE_DEMO_API_BASE_URL in production')
}

export const API_BASE_URL = apiBaseUrl || ''
export const DEMO_API_BASE_URL = demoApiBaseUrl || ''

export const API_ENDPOINTS = {
  INCIDENTS: '/api/incidents',
  INCIDENT_DETAIL: (id) => `/api/incidents/${id}`,
  INCIDENT_EVIDENCE: (id) => `/api/incidents/${id}/evidence`,
  INCIDENT_APPROVE: (id) => `/api/incidents/${id}/approve`,
  INCIDENT_REJECT: (id) => `/api/incidents/${id}/reject`,
  INCIDENT_DIAGNOSE: (id) => `/api/incidents/${id}/diagnose`,
  INCIDENT_TRACE: (id) => `/api/incidents/${id}/trace`,
  INCIDENT_TRACE_ARTIFACT: (id, key) => `/api/incidents/${id}/trace/artifact?key=${encodeURIComponent(key)}`,
  ANALYTICS: '/api/analytics',
  RUNBOOKS: '/api/runbooks',
  RUNBOOK: (faultClass) => `/api/runbooks/${faultClass}`,
  HEALTH: '/api/health'
}

export const DEMO_ENDPOINTS = {
  INJECT: '/demo/inject',
  APPROVE: (id) => `/demo/approve/${id}`
}

// Config error state for production builds with missing env vars
export let configError = null
if (isProduction && (!apiBaseUrl || !demoApiBaseUrl)) {
  configError = {
    message: 'Missing required environment variables',
    details: [
      !apiBaseUrl && 'VITE_API_BASE_URL is not set',
      !demoApiBaseUrl && 'VITE_DEMO_API_BASE_URL is not set',
    ].filter(Boolean),
    help: 'Set VITE_API_BASE_URL and VITE_DEMO_API_BASE_URL in your production environment (e.g., from CloudFormation stack outputs). See infra/template.yaml outputs DashboardApiUrl and DemoControlApiUrl.'
  }
}

// API client with error handling
class ApiClient {
  constructor(baseURL = API_BASE_URL, demoBaseURL = DEMO_API_BASE_URL) {
    this.baseURL = baseURL
    this.demoBaseURL = demoBaseURL
  }

  async request(endpoint, options = {}, useDemoURL = false) {
    const baseURL = useDemoURL ? this.demoBaseURL : this.baseURL
    const url = `${baseURL}${endpoint}`
    
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    }

    try {
      const response = await fetch(url, config)
      let json = null
      try {
        json = await response.json()
      } catch (e) {
        json = null
      }

      if (!response.ok) {
        const errMsg = json?.error || json?.message || `HTTP error! status: ${response.status}`
        throw new Error(errMsg)
      }

      // Unwrap the backend envelope { data: ..., error: ... }
      // Both main API and demo API use this envelope format
      if (json !== null && typeof json === 'object' && 'data' in json) {
        if (json.error) throw new Error(json.error)
        return json.data
      }

      return json
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error)
      throw error
    }
  }

  async get(endpoint, params = {}, useDemoURL = false) {
    const queryString = new URLSearchParams(params).toString()
    const url = queryString ? `${endpoint}?${queryString}` : endpoint
    return this.request(url, { method: 'GET' }, useDemoURL)
  }

  async post(endpoint, data = {}, useDemoURL = false) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    }, useDemoURL)
  }

  // Incident API methods (use main API)
  // Returns { items: [], next_token: string|null, count: number }
  async getIncidents(params = {}) {
    return this.get(API_ENDPOINTS.INCIDENTS, params)
  }

  async getIncidentDetail(incidentId) {
    return this.get(API_ENDPOINTS.INCIDENT_DETAIL(incidentId))
  }

  async getIncidentEvidence(incidentId) {
    return this.get(API_ENDPOINTS.INCIDENT_EVIDENCE(incidentId))
  }

  async getAnalytics() {
    return this.get(API_ENDPOINTS.ANALYTICS)
  }

  async getRunbooks() {
    return this.get(API_ENDPOINTS.RUNBOOKS)
  }

  async getRunbook(faultClass) {
    return this.get(API_ENDPOINTS.RUNBOOK(faultClass))
  }

  async getHealth() {
    return this.get(API_ENDPOINTS.HEALTH)
  }

  async getServices() {
    return this.get('/api/services')
  }

  async approveIncidentMain(incidentId) {
    return this.post(API_ENDPOINTS.INCIDENT_APPROVE(incidentId), {})
  }

  async rejectIncidentMain(incidentId, reason = '') {
    return this.post(API_ENDPOINTS.INCIDENT_REJECT(incidentId), { reason })
  }

  // Demo Mode API methods (use demo control API)
  async injectFault(faultClass) {
    return this.post(DEMO_ENDPOINTS.INJECT, { fault_class: faultClass }, true)
  }

  async approveIncident(incidentId) {
    return this.post(DEMO_ENDPOINTS.APPROVE(incidentId), {}, true)
  }

  async triggerDiagnosis(incidentId) {
    return this.post(API_ENDPOINTS.INCIDENT_DIAGNOSE(incidentId), {})
  }

  async getIncidentTrace(incidentId) {
    return this.get(API_ENDPOINTS.INCIDENT_TRACE(incidentId))
  }

  async getIncidentTraceArtifact(incidentId, key) {
    return this.get(API_ENDPOINTS.INCIDENT_TRACE_ARTIFACT(incidentId, key))
  }
}

export const apiClient = new ApiClient()
export default apiClient