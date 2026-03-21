import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// Create axios instance
export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token and organization context
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Add organization context header
    const currentOrg = localStorage.getItem('current_organization')
    if (currentOrg) {
      try {
        const org = JSON.parse(currentOrg)
        config.headers['X-Organization-ID'] = org.id
      } catch (e) {
        console.error('Failed to parse current organization:', e)
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // If 401 and not already retried, try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          const response = await axios.post(`${API_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })

          const { access_token } = response.data
          localStorage.setItem('access_token', access_token)

          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        }
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password })
    return response.data
  },

  register: async (data: {
    email: string
    username: string
    password: string
    first_name?: string
    last_name?: string
  }) => {
    const response = await api.post('/auth/register', data)
    return response.data
  },

  logout: async () => {
    await api.post('/auth/logout')
  },

  getCurrentUser: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },
}

// Users API
export const usersApi = {
  getProfile: async () => {
    const response = await api.get('/users/me')
    return response.data
  },

  updateProfile: async (data: { first_name?: string; last_name?: string; email?: string }) => {
    const response = await api.patch('/users/me', data)
    return response.data
  },
}

// VMs API
export const vmsApi = {
  list: async (params?: { page?: number; per_page?: number; status?: string; search?: string }) => {
    const response = await api.get('/vms', { params })
    return response.data
  },

  get: async (vmId: string) => {
    const response = await api.get(`/vms/${vmId}`)
    return response.data
  },

  create: async (data: {
    name: string
    hostname?: string
    description?: string
    cpu_cores: number
    cpu_sockets?: number
    memory_mb: number
    disks: Array<{
      size_gb: number
      storage_pool?: string
      disk_interface?: string
      disk_format?: string
      is_boot_disk?: boolean
    }>
    iso_image_id?: string
    boot_order?: string
    os_type?: string
    tags?: string[]
  }) => {
    const response = await api.post('/vms', data)
    return response.data
  },

  update: async (vmId: string, data: {
    name?: string
    hostname?: string
    description?: string
    cpu_cores?: number
    memory_mb?: number
  }) => {
    const response = await api.patch(`/vms/${vmId}`, data)
    return response.data
  },

  delete: async (vmId: string) => {
    await api.delete(`/vms/${vmId}`)
  },

  start: async (vmId: string) => {
    const response = await api.post(`/vms/${vmId}/start`)
    return response.data
  },

  stop: async (vmId: string, force = false) => {
    const response = await api.post(`/vms/${vmId}/stop`, { force })
    return response.data
  },

  restart: async (vmId: string) => {
    const response = await api.post(`/vms/${vmId}/restart`)
    return response.data
  },

  sync: async (vmId: string) => {
    const response = await api.post(`/vms/${vmId}/sync`)
    return response.data
  },

  getConsole: async (vmId: string) => {
    const response = await api.get(`/vms/${vmId}/console`)
    return response.data
  },

  forceStop: async (vmId: string) => {
    const response = await api.post(`/vms/${vmId}/force-stop`)
    return response.data
  },

  reboot: async (vmId: string) => {
    const response = await api.post(`/vms/${vmId}/reboot`)
    return response.data
  },

  reset: async (vmId: string) => {
    const response = await api.post(`/vms/${vmId}/reset`)
    return response.data
  },

  resize: async (vmId: string, data: {
    cpu_cores?: number
    cpu_sockets?: number
    memory_mb?: number
  }) => {
    const response = await api.patch(`/vms/${vmId}/resize`, data)
    return response.data
  },
}

// Clusters API
export const clustersApi = {
  list: async (params?: { page?: number; per_page?: number; is_active?: boolean; search?: string }) => {
    const response = await api.get('/clusters', { params })
    return response.data
  },

  get: async (clusterId: string) => {
    const response = await api.get(`/clusters/${clusterId}`)
    return response.data
  },

  create: async (data: {
    name: string
    api_url: string
    api_username: string
    datacenter?: string
    region?: string
    api_token_id?: string
    api_token_secret?: string
    api_password?: string
    verify_ssl?: boolean
    is_active?: boolean
  }) => {
    const response = await api.post('/clusters', data)
    return response.data
  },

  update: async (clusterId: string, data: {
    name?: string
    datacenter?: string
    region?: string
    api_url?: string
    api_username?: string
    api_token_id?: string
    api_token_secret?: string
    api_password?: string
    verify_ssl?: boolean
    is_active?: boolean
  }) => {
    const response = await api.patch(`/clusters/${clusterId}`, data)
    return response.data
  },

  delete: async (clusterId: string) => {
    await api.delete(`/clusters/${clusterId}`)
  },

  test: async (data: {
    api_url: string
    api_username: string
    api_token_id?: string
    api_token_secret?: string
    api_password?: string
    verify_ssl?: boolean
  }) => {
    const response = await api.post('/clusters/test', data)
    return response.data
  },

  sync: async (clusterId: string) => {
    const response = await api.post(`/clusters/${clusterId}/sync`)
    return response.data
  },
}

// Organizations API
export const organizationsApi = {
  listMyOrganizations: async () => {
    const response = await api.get('/organizations/me')
    return response.data
  },

  listMembers: async () => {
    const response = await api.get('/organizations/members')
    return response.data
  },

  inviteMember: async (data: { user_id: string; role: string }) => {
    const response = await api.post('/organizations/members', data)
    return response.data
  },

  updateMemberRole: async (userId: string, role: string) => {
    const response = await api.patch(`/organizations/members/${userId}`, { role })
    return response.data
  },

  removeMember: async (userId: string) => {
    await api.delete(`/organizations/members/${userId}`)
  },
}

// Quotas API
export const quotasApi = {
  getQuotas: async () => {
    const response = await api.get('/quotas')
    return response.data
  },

  getUsage: async () => {
    const response = await api.get('/quotas/usage')
    return response.data
  },

  updateLimit: async (resourceType: string, limitValue: number) => {
    const response = await api.put(`/quotas/${resourceType}`, { limit_value: limitValue })
    return response.data
  },

  recalculate: async () => {
    const response = await api.post('/quotas/recalculate')
    return response.data
  },
}

// ISOs API
export const isosApi = {
  list: async (params?: { page?: number; per_page?: number; include_public?: boolean; os_type?: string }) => {
    const response = await api.get('/isos', { params })
    return response.data
  },

  get: async (isoId: string) => {
    const response = await api.get(`/isos/${isoId}`)
    return response.data
  },

  upload: async (file: File, metadata: {
    name: string
    display_name: string
    description?: string
    os_type?: string
    os_version?: string
    architecture?: string
    is_public?: boolean
  }) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', metadata.name)
    formData.append('display_name', metadata.display_name)
    if (metadata.description) formData.append('description', metadata.description)
    if (metadata.os_type) formData.append('os_type', metadata.os_type)
    if (metadata.os_version) formData.append('os_version', metadata.os_version)
    if (metadata.architecture) formData.append('architecture', metadata.architecture)
    if (metadata.is_public !== undefined) formData.append('is_public', metadata.is_public.toString())

    const response = await api.post('/isos/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  uploadFromURL: async (data: {
    url: string
    display_name: string
    description?: string
    os_type?: string
    os_version?: string
    architecture?: string
    is_public?: boolean
  }) => {
    const response = await api.post('/isos/upload-from-url', data)
    return response.data
  },

  update: async (isoId: string, data: {
    display_name?: string
    description?: string
    os_type?: string
    os_version?: string
    is_public?: boolean
  }) => {
    const response = await api.patch(`/isos/${isoId}`, data)
    return response.data
  },

  delete: async (isoId: string) => {
    await api.delete(`/isos/${isoId}`)
  },
}

// Storage Pools API
export const storageApi = {
  listPools: async (clusterId: string, contentType?: string) => {
    const response = await api.get(`/storage/clusters/${clusterId}/pools`, {
      params: contentType ? { content_type: contentType } : {},
    })
    return response.data
  },

  getPool: async (clusterId: string, poolId: string) => {
    const response = await api.get(`/storage/clusters/${clusterId}/pools/${poolId}`)
    return response.data
  },

  syncPools: async (clusterId: string) => {
    const response = await api.post(`/storage/clusters/${clusterId}/pools/sync`)
    return response.data
  },

  listAllAccessible: async (contentType?: string) => {
    const response = await api.get('/storage/pools', {
      params: contentType ? { content_type: contentType } : {},
    })
    return response.data
  },
}

// VM Disks API
export const disksApi = {
  listVmDisks: async (vmId: string) => {
    const response = await api.get(`/vms/${vmId}/disks`)
    return response.data
  },

  attachDisk: async (vmId: string, data: {
    size_gb: number
    storage_pool: string
    disk_interface?: string
    disk_format?: string
  }) => {
    const response = await api.post(`/vms/${vmId}/disks`, data)
    return response.data
  },

  detachDisk: async (vmId: string, diskId: string) => {
    await api.delete(`/vms/${vmId}/disks/${diskId}`)
  },

  attachISO: async (vmId: string, isoImageId: string) => {
    const response = await api.post(`/vms/${vmId}/disks/attach-iso`, { iso_image_id: isoImageId })
    return response.data
  },

  resizeDisk: async (vmId: string, diskId: string, newSizeGb: number) => {
    const response = await api.patch(`/vms/${vmId}/disks/${diskId}/resize`, { new_size_gb: newSizeGb })
    return response.data
  },
}

export const snapshotsApi = {
  listVmSnapshots: async (vmId: string) => {
    const response = await api.get(`/vms/${vmId}/snapshots`)
    return response.data
  },

  createSnapshot: async (vmId: string, data: {
    name: string
    description?: string
    include_memory?: boolean
  }) => {
    const response = await api.post(`/vms/${vmId}/snapshots`, data)
    return response.data
  },

  rollbackSnapshot: async (vmId: string, snapshotName: string) => {
    const response = await api.post(`/vms/${vmId}/snapshots/${snapshotName}/rollback`)
    return response.data
  },

  deleteSnapshot: async (vmId: string, snapshotName: string) => {
    await api.delete(`/vms/${vmId}/snapshots/${snapshotName}`)
  },
}

// Networks API
export const networksApi = {
  list: async (page = 1, perPage = 20) => {
    const response = await api.get('/networks', {
      params: { page, per_page: perPage }
    })
    return response.data
  },

  get: async (networkId: string) => {
    const response = await api.get(`/networks/${networkId}`)
    return response.data
  },

  create: async (data: {
    name: string
    cidr: string
    description?: string
    gateway?: string
    dns_servers?: string[]
    is_shared?: boolean
    bridge?: string
  }) => {
    const response = await api.post('/networks', data)
    return response.data
  },

  update: async (networkId: string, data: {
    name?: string
    description?: string
    gateway?: string
    dns_servers?: string[]
    is_shared?: boolean
  }) => {
    const response = await api.patch(`/networks/${networkId}`, data)
    return response.data
  },

  delete: async (networkId: string) => {
    await api.delete(`/networks/${networkId}`)
  },

  setDefault: async (networkId: string) => {
    const response = await api.post(`/networks/${networkId}/set-default`)
    return response.data
  },

  getStats: async (networkId: string) => {
    const response = await api.get(`/networks/${networkId}/stats`)
    return response.data
  },

  // IP Pools
  createIpPool: async (networkId: string, data: {
    pool_name: string
    start_ip: string
    end_ip: string
    description?: string
  }) => {
    const response = await api.post(`/networks/${networkId}/ip-pools`, data)
    return response.data
  },

  listIpPools: async (networkId: string) => {
    const response = await api.get(`/networks/${networkId}/ip-pools`)
    return response.data
  },

  deleteIpPool: async (poolId: string) => {
    await api.delete(`/networks/ip-pools/${poolId}`)
  },

  // IP Allocations
  allocateIp: async (networkId: string, data?: {
    ip_pool_id?: string
    preferred_ip?: string
  }) => {
    const response = await api.post(`/networks/${networkId}/allocate-ip`, data || {})
    return response.data
  },

  listIpAllocations: async (networkId: string, status?: string) => {
    const response = await api.get(`/networks/${networkId}/ip-allocations`, {
      params: status ? { status_filter: status } : {}
    })
    return response.data
  },

  releaseIp: async (allocationId: string) => {
    await api.delete(`/networks/ip-allocations/${allocationId}`)
  },

  // VM Network Attachment
  attachToVm: async (vmId: string, data: {
    network_id: string
    interface_order: number
    model?: string
    allocate_ip?: boolean
    ip_pool_id?: string
  }) => {
    const response = await api.post(`/vms/${vmId}/attach-network`, data)
    return response.data
  },

  detachFromVm: async (vmId: string, interfaceName: string) => {
    await api.delete(`/vms/${vmId}/detach-network/${interfaceName}`)
  },
}

export default api
