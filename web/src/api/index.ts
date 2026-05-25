import { http } from './http'

export interface ApiResponse<T = unknown> {
  code: number
  msg: string
  data: T
  total?: number
  page?: number
  page_size?: number
}

export interface UserInfo {
  id?: number
  username: string
  email: string
  is_active?: boolean
  is_superuser?: boolean
}

export interface RoleRecord {
  id: number
  name: string
  desc: string
  created_at?: string
  updated_at?: string
}

export interface MenuRecord {
  id: number
  name: string
  path: string
  component: string
  icon?: string
  parent_id: number
  order: number
}

export interface ApiRecord {
  id: number
  path: string
  method: string
  summary: string
  tags: string
  unique_id: string
}

export type EtfTimeRange = '3y' | '5y' | 'all'

export interface EtfMonitorRecord {
  code: string
  name: string
  monitor?: boolean
  is_active: boolean
  time_range: EtfTimeRange
  x_drop: number
  y_step: number
  current_stage: number
  current_price?: number | null
  change_percent?: number | null
  peak_price?: number | null
  retract?: number | null
  current_retract?: number | null
  range_warning?: string | null
  range_notice?: string | null
}

export interface EtfKlineRecord {
  date: string
  open: number
  close: number
  high: number
  low: number
}

export interface EtfMinuteRecord {
  time: string
  price: number
  volume?: number | null
}

export interface EtfFundamentalInfo {
  aum?: string | null
  valuation?: string | null
  holdings?: Array<{ name: string; percent?: string | number | null }>
}

export interface EtfDetailRecord {
  code: string
  name: string
  monitor?: boolean
  is_active?: boolean
  time_range: EtfTimeRange
  x_drop: number
  y_step: number
  current_stage: number
  current_price?: number | null
  peak_price?: number | null
  trigger_price?: number | null
  retract?: number | null
  current_retract?: number | null
  range_warning?: string | null
  range_notice?: string | null
  kline?: EtfKlineRecord[]
  klines: EtfKlineRecord[]
  intraday?: EtfMinuteRecord[]
  minutes: EtfMinuteRecord[]
  fundamental?: EtfFundamentalInfo | null
  fundamentals?: EtfFundamentalInfo | null
}

export const api = {
  login: (data: { username: string; password: string }) =>
    http.post<unknown, ApiResponse<{ access_token: string; username: string }>>('/base/access_token', data),
  getUserInfo: () => http.get<unknown, ApiResponse<UserInfo>>('/base/userinfo'),
  updateProfile: (data: { email: string }) => http.post<unknown, ApiResponse<UserInfo>>('/base/profile', data),
  getRoleList: (params: { page: number; page_size: number; role_name?: string }) =>
    http.get<unknown, ApiResponse<RoleRecord[]>>('/role/list', { params }),
  createRole: (data: { name: string; desc: string }) => http.post<unknown, ApiResponse<RoleRecord>>('/role/create', data),
  updateRole: (data: { id: number; name: string; desc: string }) =>
    http.post<unknown, ApiResponse<RoleRecord>>('/role/update', data),
  deleteRole: (params: { role_id: number }) => http.delete<unknown, ApiResponse>('/role/delete', { params }),
  getMenus: () => http.get<unknown, ApiResponse<MenuRecord[]>>('/menu/list', { params: { page: 1, page_size: 9999 } }),
  getApis: () => http.get<unknown, ApiResponse<ApiRecord[]>>('/api/list', { params: { page: 1, page_size: 9999 } }),
  getRoleAuthorized: (params: { id: number }) =>
    http.get<unknown, ApiResponse<RoleRecord & { menus: MenuRecord[]; apis: ApiRecord[] }>>('/role/authorized', {
      params,
    }),
  updateRoleAuthorized: (data: { id: number; menu_ids: number[]; api_infos: Array<{ path: string; method: string }> }) =>
    http.post<unknown, ApiResponse>('/role/authorized', data),
  getEtfList: () => http.get<unknown, ApiResponse<EtfMonitorRecord[]>>('/etf/list'),
  createEtf: (data: { code: string; name?: string; time_range: EtfTimeRange; x_drop: number; y_step: number }) =>
    http.post<unknown, ApiResponse<EtfMonitorRecord>>('/etf/create', data),
  updateEtf: (data: {
    code: string
    name?: string
    is_active?: boolean
    monitor?: boolean
    time_range?: EtfTimeRange
    x_drop?: number
    y_step?: number
  }) => http.post<unknown, ApiResponse<EtfMonitorRecord>>('/etf/update', data),
  deleteEtf: (params: { code: string }) => http.delete<unknown, ApiResponse>('/etf/delete', { params }),
  getEtfDetail: (params: { code: string }) => http.get<unknown, ApiResponse<EtfDetailRecord>>('/etf/detail', { params }),
  syncEtf: (data: { code?: string } = {}) => http.post<unknown, ApiResponse<{ synced: number; message?: string }>>('/etf/sync', data),
  runEtfMonitor: () => http.post<unknown, ApiResponse<{ checked: number; alerted?: number }>>('/etf/monitor/run'),
}
