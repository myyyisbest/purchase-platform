import axios from 'axios'

// 动态 baseURL 三模式自适应：
// 1) 子路径模式（nginx 反代）：URL 路径以 /purchase-platform/ 开头，且端口为 80/443 → 走 nginx 子路径 /purchase-platform/api
// 2) 直连开发模式（vite dev server，端口 3001）：走 vite proxy /api → 后端 8000
// 3) 兜底（CloudRun 直连）：使用相对 /api
//
// 关键判断：必须同时看端口 + 路径，不能只看路径
// （vite dev 模式下 SPA 回退会让 /purchase-platform/login 的 pathname 也以子路径开头，误判会拼出错误 baseURL）
const isSubPath =
  (window.location.port === '' || window.location.port === '80' || window.location.port === '443') &&
  window.location.pathname.startsWith('/purchase-platform/')

const apiBaseURL = isSubPath
  ? '/purchase-platform/api'                      // nginx 子路径反代
  : '/api'                                        // 开发模式（vite proxy）+ 直连模式

const request = axios.create({
  baseURL: apiBaseURL,
  timeout: 60000,
  // 数组参数序列化为 company_codes=1000&company_codes=2000（FastAPI 期望的格式）
  paramsSerializer: {
    indexes: null  // 不添加 [] 后缀
  }
})

// 请求拦截：自动添加 Authorization header
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('pp_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截：解包数据 + 401 跳转登录
request.interceptors.response.use(
  response => {
    if (response.config.responseType === 'blob') {
      return response.data
    }
    const body = response.data
    // 如果是 {code, data} 结构，解包 data
    if (body && typeof body === 'object' && 'code' in body && 'data' in body) {
      return body.data
    }
    return body
  },
  error => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('pp_token')
      localStorage.removeItem('pp_user')
      // 避免在登录页重复跳转
      if (!window.location.pathname.endsWith('/login')) {
        const base = isSubPath ? '/purchase-platform' : ''
        window.location.href = `${base}/login`
      }
    }
    console.error('API请求失败:', error)
    return Promise.reject(error)
  }
)

export default request
