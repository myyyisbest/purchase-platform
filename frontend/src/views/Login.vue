<template>
  <div class="login-container">
    <!-- 左侧品牌展示区（办公风深蓝灰，小屏隐藏） -->
    <aside class="brand-panel">
      <div class="brand-top">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 3h18v4H3zM3 10h18v4H3zM3 17h18v4H3z" />
          </svg>
        </div>
        <span class="brand-name">采购分析平台</span>
      </div>
      <div class="brand-body">
        <h1>数据驱动<br />采购决策</h1>
        <p class="brand-sub">覆盖价格分析、趋势监测、异常采购与汇总看板的综合分析平台</p>
        <ul class="brand-features">
          <li><span class="dot"></span>多维度价格对比与趋势可视化</li>
          <li><span class="dot"></span>异常采购自动识别与预警</li>
          <li><span class="dot"></span>实时汇总看板，决策有据可依</li>
        </ul>
      </div>
      <div class="brand-footer">© 采购分析平台</div>
    </aside>

    <!-- 右侧登录表单区 -->
    <main class="form-panel">
      <div class="login-card">
        <div class="login-header">
          <h2>欢迎登录</h2>
          <p>请输入您的账户信息</p>
        </div>
        <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin" class="login-form">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="用户名"
              prefix-icon="User"
              size="large"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              prefix-icon="Lock"
              size="large"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 强制修改密码弹窗 -->
      <el-dialog v-model="changePwdVisible" title="修改密码" width="420px" :close-on-click-modal="false" :show-close="false">
        <el-alert type="warning" :closable="false" style="margin-bottom: 16px">
          首次登录或使用默认密码，请修改密码后继续使用。
        </el-alert>
        <el-form :model="pwdForm" :rules="pwdRules" ref="pwdFormRef">
          <el-form-item label="旧密码" prop="oldPassword">
            <el-input v-model="pwdForm.oldPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码" prop="newPassword">
            <el-input v-model="pwdForm.newPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input v-model="pwdForm.confirmPassword" type="password" show-password />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">确认修改</el-button>
        </template>
      </el-dialog>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, changePassword } from '../api/auth'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const changePwdVisible = ref(false)
const pwdLoading = ref(false)
const pwdFormRef = ref(null)
const pwdForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

const validateConfirm = (rule, value, callback) => {
  if (value !== pwdForm.newPassword) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const pwdRules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const res = await login(form.username, form.password)
    // 存储 token 和用户信息
    localStorage.setItem('pp_token', res.access_token)
    localStorage.setItem('pp_user', JSON.stringify(res.user))

    if (res.user.must_change_password) {
      // 强制修改密码
      changePwdVisible.value = true
      pwdForm.oldPassword = form.password
    } else {
      router.push('/dashboard')
    }
  } catch (e) {
    const msg = e.response?.data?.detail || '登录失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function handleChangePassword() {
  await pwdFormRef.value?.validate()
  pwdLoading.value = true
  try {
    await changePassword(pwdForm.oldPassword, pwdForm.newPassword)
    ElMessage.success('密码修改成功')
    changePwdVisible.value = false
    // 更新本地用户信息
    const user = JSON.parse(localStorage.getItem('pp_user') || '{}')
    user.must_change_password = false
    localStorage.setItem('pp_user', JSON.stringify(user))
    router.push('/dashboard')
  } catch (e) {
    const msg = e.response?.data?.detail || '修改密码失败'
    ElMessage.error(msg)
  } finally {
    pwdLoading.value = false
  }
}
</script>

<style scoped>
/* 整体左右分栏：左品牌展示 + 右表单 */
.login-container {
  height: 100vh;
  display: flex;
}

/* 左侧品牌区：商务深蓝灰渐变 */
.brand-panel {
  flex: 1.1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 48px 56px;
  color: #f1f5f9;
  background: linear-gradient(160deg, #0f172a 0%, #1e293b 55%, #334155 100%);
  position: relative;
  overflow: hidden;
}
/* 背景几何点缀，增加质感但不喧宾夺主 */
.brand-panel::before {
  content: '';
  position: absolute;
  top: -120px;
  right: -120px;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.18) 0%, transparent 70%);
}
.brand-panel::after {
  content: '';
  position: absolute;
  bottom: -80px;
  left: -80px;
  width: 280px;
  height: 280px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(148, 163, 184, 0.12) 0%, transparent 70%);
}
.brand-top {
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
  z-index: 1;
}
.brand-logo {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.brand-name {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.brand-body {
  position: relative;
  z-index: 1;
}
.brand-body h1 {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.3;
  margin-bottom: 18px;
}
.brand-sub {
  font-size: 15px;
  color: #cbd5e1;
  line-height: 1.7;
  margin-bottom: 36px;
  max-width: 420px;
}
.brand-features {
  list-style: none;
  padding: 0;
  margin: 0;
}
.brand-features li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #e2e8f0;
  margin-bottom: 14px;
}
.brand-features .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #60a5fa;
  flex-shrink: 0;
}
.brand-footer {
  font-size: 12px;
  color: #64748b;
  position: relative;
  z-index: 1;
}

/* 右侧表单区 */
.form-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
}
.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 48px 40px 32px;
  width: 380px;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
  border: 1px solid #e2e8f0;
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}
.login-header p {
  color: #64748b;
  font-size: 14px;
}
.login-form :deep(.el-input__wrapper) {
  border-radius: 6px;
}
.login-btn {
  width: 100%;
  background: #2563eb;
  border-color: #2563eb;
}
.login-btn:hover,
.login-btn:focus {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

/* 中等屏幕：左侧收窄 */
@media (max-width: 1100px) {
  .brand-panel {
    flex: 0.9;
    padding: 40px 36px;
  }
  .brand-body h1 {
    font-size: 30px;
  }
}
/* 小屏：隐藏左侧品牌区，仅显示表单 */
@media (max-width: 768px) {
  .brand-panel {
    display: none;
  }
  .form-panel {
    flex: 1;
  }
}
</style>
