<script setup>
import { computed, onMounted, ref } from 'vue'
import CrawlWorkspace from './components/CrawlWorkspace.vue'
import MusicWorkspace from './components/MusicWorkspace.vue'
import BookSearchWorkspace from './components/BookSearchWorkspace.vue'
import VersionDialog from './components/VersionDialog.vue'
import { initLicense, license } from './license'

const isDark = ref(false)
const showVersion = ref(false)
const guideOpen = ref(true)
const workspace = ref('image')
const workspaceTabs = [
  { label: '图片', value: 'image', icon: 'Picture' },
  { label: '音乐', value: 'music', icon: 'Headset' },
  { label: '小说', value: 'novel', icon: 'Notebook' },
  { label: '漫画', value: 'comic', icon: 'Film' },
  { label: '教材', value: 'books', icon: 'Reading' },
]

const versionLabel = computed(() => (license.version === 'plus' ? 'Plus' : 'Lite'))

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  try {
    localStorage.setItem('wanpa-theme', isDark.value ? 'dark' : 'light')
  } catch (e) {}
}

onMounted(() => {
  initLicense()
  isDark.value = document.documentElement.getAttribute('data-theme') === 'dark'
  guideOpen.value = window.innerWidth >= 992
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
          <span class="sub">图片 / 小说 / 漫画 多源批量爬取</span>
        </div>
        <div class="head-actions">
          <button class="version-btn" type="button" @click="showVersion = true">
            <span class="version-dot" :class="versionLabel.toLowerCase()"></span>
            {{ versionLabel }}
            <span class="version-caret">切换</span>
          </button>
          <el-tooltip :content="isDark ? '切换到浅色' : '切换到暗色'" placement="bottom" effect="light">
            <button class="theme-btn" type="button" @click="toggleTheme" :aria-label="isDark ? '切换到浅色' : '切换到暗色'">
              <el-icon v-if="isDark" :size="20"><Sunny /></el-icon>
              <el-icon v-else :size="20"><Moon /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </el-header>
      <el-main class="main">
        <el-alert class="guide" type="error" :closable="false">
          <template #title>
            <button class="guide-toggle" type="button" @click="guideOpen = !guideOpen">
              <span>使用指南与注意事项</span>
              <span class="guide-caret" :class="{ open: guideOpen }">▾</span>
            </button>
          </template>
          <div v-show="guideOpen" class="guide-body">
            <p><b>使用指南：</b>切换「图片 / 音乐 / 小说 / 漫画 / 教材」模式，输入关键词并勾选数据源（Lite 版使用免费国内源；Plus 版解锁海外图库、漫画、AI 摘要等全部功能，点击右上角版本按钮可开通）。可添加「多层筛选」规则，对搜索结果逐层过滤（层间取交集，层内关键词取并集）；小说支持阅读与 AI 摘要，完成后可打包 ZIP 下载。更多操作请见右侧各区域提示。</p>
            <p><b>禁止事项：</b>请仅将本工具用于合法、个人学习用途，遵守目标网站的使用条款与 robots 协议，尊重版权，严禁用于任何违反法律法规的行为。</p>
            <p><b>注意：</b>请合理控制并发与数量，避免对目标站点造成压力；本站仅提供技术演示，使用者需自行承担相关责任。</p>
          </div>
        </el-alert>
        <div class="workspace-tabs">
          <button
            v-for="tab in workspaceTabs"
            :key="tab.value"
            class="ws-tab"
            :class="{ active: workspace === tab.value }"
            @click="workspace = tab.value"
          >{{ tab.label }}</button>
        </div>
        <CrawlWorkspace v-if="workspace === 'image' || workspace === 'novel' || workspace === 'comic'" :mode="workspace" />
        <MusicWorkspace v-else-if="workspace === 'music'" :active="workspace === 'music'" />
        <BookSearchWorkspace v-else-if="workspace === 'books'" />
      </el-main>
    </el-container>
    <VersionDialog v-model="showVersion" />
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
.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.version-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card-soft);
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.version-btn:hover {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.version-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}
.version-dot.lite {
  background: #909399;
}
.version-dot.plus {
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);
}
.version-caret {
  color: var(--text-sub);
  font-weight: 400;
  font-size: 12px;
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
.guide {
  margin-bottom: 16px;
}
.guide-title {
  font-weight: 700;
}
.guide-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}
.guide-caret {
  transition: transform 0.2s ease;
  font-size: 12px;
  color: var(--text-sub);
}
.guide-caret.open {
  transform: rotate(180deg);
}
.guide-body {
  font-size: 13px;
  line-height: 1.7;
}
.guide-body p {
  margin: 4px 0;
  color: #f56c6c;
}

.workspace-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--card);
}
.ws-tab {
  flex: 1;
  padding: 8px 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-sub);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.ws-tab:hover {
  color: var(--text);
  background: var(--card-soft);
}
.ws-tab.active {
  color: #fff;
  background: var(--brand);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}

@media (max-width: 991px) {
  .header {
    height: 56px;
    padding: 0 12px;
  }
  .logo {
    width: 30px;
    height: 30px;
  }
  .brand-title {
    font-size: 18px;
    letter-spacing: 0.5px;
  }
  .sub {
    display: none;
  }
  .main {
    padding: 12px 10px calc(64px + env(safe-area-inset-bottom));
  }
  .guide {
    margin-bottom: 12px;
  }
  .guide-body {
    font-size: 12px;
  }
  .version-btn {
    padding: 5px 10px;
    font-size: 12px;
  }
  .theme-btn {
    width: 34px;
    height: 34px;
  }
}

</style>
