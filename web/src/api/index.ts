import { http } from './http'

export interface ApiResponse<T = unknown> {
  code: number
  msg: string
  data: T
  total?: number
  page?: number
  page_size?: number
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

export const api = {
  login: (data: { username: string; password: string }) =>
    http.post<unknown, ApiResponse<{ access_token: string; username: string }>>('/base/access_token', data),
  getUserInfo: () => http.get<unknown, ApiResponse<{ username: string }>>('/base/userinfo'),
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
}
