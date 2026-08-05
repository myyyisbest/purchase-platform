<template>
  <div class="change-pwd-container">
    <div class="change-pwd-card">
      <h2>修改密码</h2>
      <p>为了账户安全，请定期修改密码</p>
      <el-form :model="form" :rules="rules" ref="formRef" style="margin-top: 24px">
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input v-model="form.oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="form.newPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSubmit">确认修改</el-button>
          <el-button @click="$router.push('/dashboard')">返回</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { changePassword } from '../api/auth'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

const validateConfirm = (rule, value, callback) => {
  if (value !== form.newPassword) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleSubmit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await changePassword(form.oldPassword, form.newPassword)
    ElMessage.success('密码修改成功')
    // 更新本地信息
    const user = JSON.parse(localStorage.getItem('pp_user') || '{}')
    user.must_change_password = false
    localStorage.setItem('pp_user', JSON.stringify(user))
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.change-pwd-container {
  max-width: 500px;
  margin: 60px auto;
}
.change-pwd-card {
  background: #fff;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.change-pwd-card h2 {
  margin-bottom: 4px;
}
.change-pwd-card p {
  color: #909399;
  font-size: 13px;
}
</style>
