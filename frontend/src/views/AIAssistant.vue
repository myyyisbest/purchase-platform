<template>
  <div class="copilot"></div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'

let timer = null

onMounted(() => {
  const script = document.createElement('script')
  script.defer = true
  script.async = true
  // AI 助手服务地址，请通过环境变量 VITE_AI_ASSISTANT_URL 配置
  script.src = `${import.meta.env.VITE_AI_ASSISTANT_URL || ''}/xpack_static/sqlbot-embedded-dynamic.umd.js`
  document.head.appendChild(script)

  timer = setInterval(() => {
    if (sqlbot_embedded_handler?.mounted) {
      // 嵌入式 ID，请通过环境变量 VITE_AI_EMBEDDED_ID 配置
      sqlbot_embedded_handler.mounted('.copilot', { embeddedId: import.meta.env.VITE_AI_EMBEDDED_ID || '' })
      clearInterval(timer)
      timer = null
    }
  }, 1000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.copilot {
  height: calc(100vh - 140px);
  width: 100%;
}
</style>
