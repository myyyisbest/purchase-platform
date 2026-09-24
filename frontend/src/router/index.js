import { createRouter, createWebHistory } from 'vue-router'

// 路由配置
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', noAuth: true }
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: () => import('../views/ChangePassword.vue'),
    meta: { title: '修改密码', noAuth: true }
  },
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '采购概览看板' }
  },
  {
    path: '/purchase-anomaly',
    name: 'PurchaseAnomaly',
    component: () => import('../views/PurchaseAnomaly.vue'),
    meta: { title: '采购异常监测' }
  },
  {
    path: '/price-trend',
    name: 'PriceTrend',
    component: () => import('../views/PriceTrend.vue'),
    meta: { title: '物料单价趋势' }
  },
  {
    path: '/exchange-rate',
    name: 'ExchangeRate',
    component: () => import('../views/ExchangeRate.vue'),
    meta: { title: '汇率管理', requiresAdmin: true }
  },
  {
    path: '/org-management',
    name: 'OrgManagement',
    component: () => import('../views/OrgManagement.vue'),
    meta: { title: '组织架构', requiresAdmin: true }
  },
  {
    path: '/user-management',
    name: 'UserManagement',
    component: () => import('../views/UserManagement.vue'),
    meta: { title: '用户与权限管理', requiresAdmin: true }
  },
  {
    path: '/material-major-category',
    name: 'MaterialMajorCategory',
    component: () => import('../views/MaterialMajorCategory.vue'),
    meta: { title: '物料大类维护' }
  },
  {
    path: '/yoy-analysis',
    name: 'YoYAnalysis',
    component: () => import('../views/YoYAnalysis.vue'),
    meta: { title: '采购对比分析' }
  },
  {
    path: '/purchase-records',
    name: 'PurchaseRecords',
    component: () => import('../views/PurchaseRecords.vue'),
    meta: { title: '采购记录明细' }
  },
  {
    path: '/suppliers',
    name: 'Suppliers',
    component: () => import('../views/Suppliers.vue'),
    meta: { title: '供应商管理' }
  },
  {
    path: '/data-import',
    name: 'DataImport',
    component: () => import('../views/DataImport.vue'),
    meta: { title: '数据导入', requiresAdmin: true }
  },
  {
    path: '/hana-sync',
    name: 'HanaSync',
    component: () => import('../views/HanaSync.vue'),
    meta: { title: 'HANA 同步', requiresAdmin: true }
  },
  {
    path: '/audit-logs',
    name: 'AuditLogs',
    component: () => import('../views/AuditLogs.vue'),
    meta: { title: '审计日志', requiresAdmin: true }
  },
  {
    path: '/ai-assistant',
    name: 'AIAssistant',
    component: () => import('../views/AIAssistant.vue'),
    meta: { title: 'AI 智能助手' }
  }
]

const router = createRouter({
  history: createWebHistory('/purchase-platform/'),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  document.title = to.meta.title || '采购分析平台'

  // 无需认证的路由直接放行
  if (to.meta.noAuth) {
    return next()
  }

  const token = localStorage.getItem('pp_token')
  if (!token) {
    return next('/login')
  }

  // 管理员专属页面检查
  if (to.meta.requiresAdmin) {
    try {
      const user = JSON.parse(localStorage.getItem('pp_user') || '{}')
      if (user.role !== 'admin') {
        return next('/dashboard')
      }
    } catch {
      return next('/login')
    }
  }

  next()
})

export default router
