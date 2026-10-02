<script setup>
import { onMounted, ref } from 'vue'
import CrawlWorkspace from './components/CrawlWorkspace.vue'
import MusicWorkspace from './components/MusicWorkspace.vue'
import BookSearchWorkspace from './components/BookSearchWorkspace.vue'
import VersionDialog from './components/VersionDialog.vue'
import { initLicense, license } from './license'

const isDark = ref(false)
const workspace = ref('image')
const contentWorkspace = ref('image')
const versionVisible = ref(false)
const APP_VERSION = '1.0.0'
const APP_AUTHOR = 'KeyandBoy'

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  try {
    localStorage.setItem('wanpa-theme', isDark.value ? 'dark' : 'light')
  } catch (e) {}
}

function switchWorkspace(value) {
  workspace.value = value
  if (!['books', 'music'].includes(value)) contentWorkspace.value = value
  try {
    localStorage.setItem('wanpa-workspace', value)
  } catch (e) {}
}

onMounted(() => {
  initLicense()
  isDark.value = document.documentElement.getAttribute('data-theme') === 'dark'
  try {
    const saved = localStorage.getItem('wanpa-workspace') || 'image'
    workspace.value = ['image', 'video', 'music', 'novel', 'comic', 'books'].includes(saved) ? saved : 'image'
    contentWorkspace.value = ['books', 'music'].includes(workspace.value) ? 'image' : workspace.value
  } catch (e) {}
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
          <span class="sub">多源资源爬取与教材检索</span>
          <span class="author-tag" title="本软件受自定义授权保护，仅供自用，禁止商用与二次分发">v{{ APP_VERSION }} · {{ APP_AUTHOR }}</span>
          </div>
          <div class="header-actions">
           <el-tooltip
             :content="license.version === 'plus' ? 'Plus 授权中，点击查看 / 切换回 Lite' : '当前 Lite，点击查看授权与升级'"
             placement="bottom"
             effect="light"
           >
            <button class="version-btn" type="button" @click="versionVisible = true" aria-label="版本与授权">
              <span class="version-dot" :class="license.version === 'plus' ? 'plus' : 'lite'"></span>
              <span class="version-label">{{ license.version === 'plus' ? 'Plus' : 'Lite' }}</span>
              <span class="version-caret">▾</span>
            </button>
          </el-tooltip>
           <el-tooltip :content="isDark ? '切换到浅色' : '切换到暗色'" placement="bottom" effect="light">
            <button class="theme-btn" type="button" @click="toggleTheme" :aria-label="isDark ? '切换到浅色' : '切换到暗色'">
              <el-icon v-if="isDark" :size="20"><Sunny /></el-icon>
              <el-icon v-else :size="20"><Moon /></el-icon>
            </button>
          </el-tooltip>
          <VersionDialog v-model="versionVisible" />
        </div>
      </el-header>
      <el-main class="main">
        <nav class="workspace-nav" aria-label="工作区切换">
          <button :class="{ active: workspace === 'image' }" type="button" @click="switchWorkspace('image')">
            <el-icon><Picture /></el-icon>图片
          </button>
          <button :class="{ active: workspace === 'video' }" type="button" @click="switchWorkspace('video')">
            <el-icon><VideoCamera /></el-icon>视频
          </button>
          <button :class="{ active: workspace === 'music' }" type="button" @click="switchWorkspace('music')">
            <el-icon><Headset /></el-icon>音乐
          </button>
          <button :class="{ active: workspace === 'novel' }" type="button" @click="switchWorkspace('novel')">
            <el-icon><Notebook /></el-icon>小说
          </button>
          <button :class="{ active: workspace === 'comic' }" type="button" @click="switchWorkspace('comic')">
            <el-icon><Postcard /></el-icon>漫画
          </button>
          <button :class="{ active: workspace === 'books' }" type="button" @click="switchWorkspace('books')">
            <el-icon><Reading /></el-icon>教材与电子书
          </button>
        </nav>
        <CrawlWorkspace v-show="!['books', 'music'].includes(workspace)" :mode="contentWorkspace" :active="!['books', 'music'].includes(workspace)" />
        <MusicWorkspace v-show="workspace === 'music'" :active="workspace === 'music'" />
        <BookSearchWorkspace v-show="workspace === 'books'" />
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

.header-actions { display: flex; align-items: center; gap: 8px; }
.author-tag { flex-shrink: 0; padding: 2px 8px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-sub); font-size: 11px; opacity: .75; white-space: nowrap; }
.workspace-nav { display: flex; width: fit-content; gap: 4px; margin: 0 auto 18px; padding: 4px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); box-shadow: 0 4px 16px rgba(15,23,42,.06); }
.workspace-nav button { display: inline-flex; align-items: center; gap: 7px; padding: 9px 18px; border: 0; border-radius: 8px; color: var(--text-sub); background: transparent; cursor: pointer; font-size: 13px; font-weight: 600; transition: all .2s ease; }
.workspace-nav button:hover { color: #2563eb; background: var(--card-soft); }
.workspace-nav button.active { color: #fff; background: linear-gradient(135deg, #2563eb, #0f766e); box-shadow: 0 4px 12px rgba(37,99,235,.25); }

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
  .sub, .author-tag {
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

@media (max-width: 720px) {
  .workspace-nav { width: 100%; overflow-x: auto; justify-content: flex-start; }
  .workspace-nav button { flex: 0 0 auto; justify-content: center; padding-inline: 8px; }
}

</style>
