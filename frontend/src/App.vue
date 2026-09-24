<template>
  <el-config-provider :locale="zhCn">
    <!-- 登录页不显示侧边栏 -->
    <template v-if="route.path === '/login'">
      <router-view />
    </template>
    <template v-else>
      <el-container class="app-container">
        <!-- 侧边栏 -->
        <el-aside width="200px" class="app-sidebar">
          <div class="sidebar-header">
            <h2>采购分析平台</h2>
          </div>
          <el-menu
            :default-active="activeMenu"
            class="sidebar-menu"
            background-color="#304156"
            text-color="#bfcbd9"
            active-text-color="#409EFF"
            router
          >
            <el-menu-item index="/dashboard">
              <el-icon><DataLine /></el-icon>
              <span>采购概览看板</span>
            </el-menu-item>

            <el-menu-item index="/purchase-anomaly">
              <el-icon><WarningFilled /></el-icon>
              <span>采购异常监测</span>
            </el-menu-item>
            
            <el-menu-item index="/price-trend">
              <el-icon><TrendCharts /></el-icon>
              <span>物料单价趋势</span>
            </el-menu-item>
            
            <el-menu-item index="/yoy-analysis">
              <el-icon><DataAnalysis /></el-icon>
              <span>采购对比分析</span>
            </el-menu-item>

            <el-menu-item index="/purchase-records">
              <el-icon><List /></el-icon>
              <span>采购记录明细</span>
            </el-menu-item>
            
            <el-menu-item index="/material-major-category">
              <el-icon><Files /></el-icon>
              <span>物料大类维护</span>
            </el-menu-item>

            <el-menu-item index="/ai-assistant">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI 智能助手</span>
            </el-menu-item>

            <!-- 管理员专属菜单 -->
            <template v-if="isAdmin">
              <el-menu-item index="/org-management">
                <el-icon><OfficeBuilding /></el-icon>
                <span>组织架构</span>
              </el-menu-item>
              
              <el-menu-item index="/exchange-rate">
                <el-icon><Money /></el-icon>
                <span>汇率管理</span>
              </el-menu-item>

              <el-menu-item index="/user-management">
                <el-icon><UserFilled /></el-icon>
                <span>用户与权限管理</span>
              </el-menu-item>

              <el-menu-item index="/data-import">
                <el-icon><Upload /></el-icon>
                <span>数据导入</span>
              </el-menu-item>
            </template>
          </el-menu>
        </el-aside>

        <!-- 主内容区 -->
        <el-container>
          <el-header class="app-header">
            <div class="header-left">
              <h3>{{ currentTitle }}</h3>
            </div>
            <div class="header-right">
              <el-dropdown>
                <span class="user-info">
                  <el-icon><User /></el-icon>
                  {{ displayName }}
                  <el-tag size="small" :type="isAdmin ? 'danger' : 'info'" style="margin-left: 6px">
                    {{ isAdmin ? '管理员' : '普通用户' }}
                  </el-tag>
                  <el-icon><ArrowDown /></el-icon>
                </span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="$router.push('/change-password')">修改密码</el-dropdown-item>
                    <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </el-header>
          
          <el-main class="app-main">
            <router-view />
          </el-main>
        </el-container>
      </el-container>
    </template>
  </el-config-provider>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { DataLine, TrendCharts, DataAnalysis, Money, OfficeBuilding, ChatDotRound, User, ArrowDown, Files, UserFilled, WarningFilled, Upload, List } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta.title || '采购分析平台')

// 用户状态
const userRole = ref('')
const userName = ref('')

function loadUserInfo() {
  try {
    const user = JSON.parse(localStorage.getItem('pp_user') || '{}')
    userRole.value = user.role || ''
    userName.value = user.real_name || user.username || ''
  } catch {
    userRole.value = ''
    userName.value = ''
  }
}

const isAdmin = computed(() => userRole.value === 'admin')
const displayName = computed(() => userName.value || '用户')

onMounted(() => {
  loadUserInfo()
})

// 监听路由变化，刷新用户信息
watch(() => route.path, () => {
  loadUserInfo()
})

function handleLogout() {
  localStorage.removeItem('pp_token')
  localStorage.removeItem('pp_user')
  router.push('/login')
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  width: 100%;
}

.app-container {
  height: 100vh;
}

.app-sidebar {
  background-color: #304156;
  overflow-y: auto;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.sidebar-header h2 {
  font-size: 16px;
  font-weight: 600;
}

.sidebar-menu {
  border-right: none;
}

.app-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.header-left h3 {
  font-size: 18px;
  font-weight: 500;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #606266;
}

.user-info .el-icon {
  margin: 0 5px;
}

.app-main {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
