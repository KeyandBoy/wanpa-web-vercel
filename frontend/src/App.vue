<script setup>
import { onMounted, ref } from 'vue'
import CrawlWorkspace from './components/CrawlWorkspace.vue'

const isDark = ref(false)

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  try {
    localStorage.setItem('wanpa-theme', isDark.value ? 'dark' : 'light')
  } catch (e) {}
}

onMounted(() => {
  isDark.value = document.documentElement.getAttribute('data-theme') === 'dark'
})
</script>

<template>
  <div class="page">
    <el-container>
      <el-header class="header" height="64px">
        <div class="brand">
          <svg class="logo" viewBox="0 0 48 48" width="36" height="36" aria-hidden="true">
            <defs>
              <linearGradient id="wanpaLogo" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#2563eb" />
                <stop offset="100%" stop-color="#60a5fa" />
              </linearGradient>
            </defs>
            <rect x="2" y="2" width="44" height="44" rx="12" fill="url(#wanpaLogo)" />
            <path
              d="M14 17h20M14 24h20M14 31h20M17 14v20M24 14v20M31 14v20"
              stroke="#fff"
              stroke-width="2"
              stroke-linecap="round"
              opacity="0.5"
            />
            <path
              d="M24 22v13M19 30l5 5 5-5"
              stroke="#fff"
              stroke-width="2.6"
              fill="none"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <h2 class="brand-title">万爬网</h2>
          <span class="sub">图片 / 小说 多源批量爬取</span>
        </div>
        <el-tooltip :content="isDark ? '切换到浅色' : '切换到暗色'" placement="bottom" effect="light">
          <button class="theme-btn" type="button" @click="toggleTheme" :aria-label="isDark ? '切换到浅色' : '切换到暗色'">
            <el-icon v-if="isDark" :size="20"><Sunny /></el-icon>
            <el-icon v-else :size="20"><Moon /></el-icon>
          </button>
        </el-tooltip>
      </el-header>
      <el-main class="main">
        <CrawlWorkspace />
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--card);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
  transition: background 0.25s ease, border-color 0.25s ease;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.logo {
  flex-shrink: 0;
  filter: drop-shadow(0 2px 6px rgba(37, 99, 235, 0.35));
}
.brand-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 1px;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  white-space: nowrap;
}
.sub {
  color: var(--text-sub);
  font-size: 13px;
  white-space: nowrap;
}
.theme-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card-soft);
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s ease;
}
.theme-btn:hover {
  border-color: var(--brand);
  color: var(--brand);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.main {
  padding: 18px;
}
</style>
