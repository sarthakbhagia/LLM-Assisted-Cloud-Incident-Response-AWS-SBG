// API Configuration
// In local dev: leave VITE_API_BASE_URL unset. The Vite dev server proxy
// (vite.config.js server.proxy) routes /api/* to localhost:3001 automatically.
// In production: set VITE_API_BASE_URL to your API Gateway Prod stage URL, e.g.:
//   VITE_API_BASE_URL=https://o212lf1md4.execute-api.ap-south-1.amazonaws.com/Prod
//   VITE_DEMO_API_BASE_URL=https://0l32vjl4n8.execute-api.ap-south-1.amazonaws.com/Prod
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
export const DEMO_API_BASE_URL = import.meta.env.VITE_DEMO_API_BASE_URL || ''

export const API_ENDPOINTS = {
  INCIDENTS: '/api/incidents',
  INCIDENT_DETAIL: (id) => `/api/incidents/${id}`,
  INCIDENT_EVIDENCE: (id) => `/api/incidents/${id}/evidence`,
  INCIDENT_APPROVE: (id) => `/api/incidents/${id}/approve`,
  INCIDENT_REJECT: (id) => `/api/incidents/${id}/reject`,
  ANALYTICS: '/api/analytics',
  RUNBOOKS: '/api/runbooks',
  RUNBOOK: (faultClass) => `/api/runbooks/${faultClass}`,
  HEALTH: '/health'
}

export const DEMO_ENDPOINTS = {
  INJECT: '/demo/inject',
  APPROVE: (id) => `/demo/approve/${id}`
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
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const json = await response.json()

      // Unwrap the backend envelope { data: ..., error: ... }
      // The demo control API does NOT use this envelope — skip unwrap for those
      if (!useDemoURL && json !== null && typeof json === 'object' && 'data' in json) {
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
    return this.post('/diagnose', { incident_id: incidentId })
  }
}

export const apiClient = new ApiClient()
export default apiClient