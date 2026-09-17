// API Configuration
// Update this URL when the dashboard API is deployed
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod'

export const API_ENDPOINTS = {
  INCIDENTS: '/incidents',
  INCIDENT_DETAIL: (id) => `/incidents/${id}`,
  RESULTS: '/results',
  HEALTH: '/health'
}

// API client with error handling
class ApiClient {
  constructor(baseURL = API_BASE_URL) {
    this.baseURL = baseURL
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`
    
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
      
      const data = await response.json()
      return data
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error)
      throw error
    }
  }

  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString()
    const url = queryString ? `${endpoint}?${queryString}` : endpoint
    return this.request(url, { method: 'GET' })
  }

  async post(endpoint, data = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  }

  // Incident API methods
  async getIncidents(params = {}) {
    return this.get(API_ENDPOINTS.INCIDENTS, params)
  }

  async getIncidentDetail(incidentId) {
    return this.get(API_ENDPOINTS.INCIDENT_DETAIL(incidentId))
  }

  async getResults() {
    return this.get(API_ENDPOINTS.RESULTS)
  }

  async getHealth() {
    return this.get(API_ENDPOINTS.HEALTH)
  }

  async injectFault(faultClass) {
    return this.post('/inject', { fault_class: faultClass })
  }

  async triggerDiagnosis(incidentId) {
    return this.post('/diagnose', { incident_id: incidentId })
  }
}

export const apiClient = new ApiClient()
export default apiClient