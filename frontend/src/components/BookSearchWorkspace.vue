<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const keyword = ref('')
const englishKeyword = ref('')
const selectedSource = ref('all')
const selectedLanguage = ref('all')
const selectedFormat = ref('all')
const onlyDownloadable = ref(false)
const loading = ref(false)
const loadingMore = ref(false)
const page = ref(1)
const hasMore = ref(false)
const items = ref([])
const sources = ref([])
const sourceErrors = ref({})
const sourceStats = ref({})
const accessMeta = {
  open_access: { label: '开放访问', type: 'success' },
  borrow: { label: '在线借阅', type: 'warning' },
  preview: { label: '部分预览', type: 'info' },
  metadata: { label: '书目信息', type: '' },
}

const visibleItems = computed(() => items.value.filter((item) => {
  if (selectedLanguage.value === 'zh' && !isChinese(item)) return false
  if (selectedLanguage.value === 'en' && isChinese(item)) return false
  const candidates = item.download_candidates || []
  if (onlyDownloadable.value && candidates.length === 0) return false
  if (selectedFormat.value !== 'all' && !candidates.some((candidate) => candidate.format === selectedFormat.value)) return false
  return true
}))

function isChinese(item) {
  const language = String(item.language || '').toLowerCase()
  return /[\u4e00-\u9fff]/.test(item.title || '') || ['zh', 'chi', 'zho', 'chinese'].includes(language)
}

function access(item) {
  return accessMeta[item.access_type] || accessMeta.metadata
}

function sourceLabel(item) {
  return (item.sources || [item.source]).join(' · ')
}

function openExternal(url) {
  if (!/^https?:\/\//i.test(url || '')) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function loadSources() {
  try {
    sources.value = (await api.bookSources()) || []
  } catch (error) {
    ElMessage.warning('书源列表读取失败: ' + error.message)
  }
}

async function runSearch(append = false) {
  if (!keyword.value.trim()) {
    ElMessage.warning('请输入教材名称、作者或 ISBN')
    return
  }
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const targetPage = append ? page.value + 1 : 1
    const result = await api.bookSearch({
      keyword: keyword.value.trim(),
      english_keyword: englishKeyword.value.trim(),
      source: selectedSource.value,
      page: targetPage,
      page_size: 12,
    })
    if (append) {
      const combined = [...items.value, ...(result.items || [])]
      items.value = [...new Map(combined.map((item) => [item.id || item.detail_url, item])).values()]
    } else {
      items.value = result.items || []
    }
    sourceErrors.value = result.errors || {}
    sourceStats.value = result.source_stats || {}
    page.value = targetPage
    hasMore.value = Boolean(result.has_more)
    if (!append && items.value.length === 0) {
      const allFailed = Object.keys(sourceErrors.value).length >= (selectedSource.value === 'all' ? sources.value.length : 1)
      ElMessage.info(allFailed ? '书源连接失败，请检查代理或稍后重试' : '没有找到相关教材，请尝试作者、ISBN 或英文关键词')
    }
  } catch (error) {
    ElMessage.error(error.name === 'AbortError' ? '搜索超时，请减少书源后重试' : error.message)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function openExternalSource(source) {
  if (source && source.url && /^https?:\/\//i.test(source.url)) {
    window.open(source.url, '_blank', 'noopener,noreferrer')
  }
}

function downloadBook(item, candidate) {
  if (!candidate) return
  const ext = candidate.format || ''
  const safe = (item.title || 'book').replace(/[^\w\u4e00-\u9fff -]/g, '_').slice(0, 80)
  const filename = `${safe}.${ext}`
  const a = document.createElement('a')
  a.href = api.bookDownloadUrl(candidate.url, filename, ext)
  a.download = filename
  a.target = '_blank'
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  ElMessage.success('正在下载...')
}

onMounted(loadSources)
</script>

<template>
  <section class="book-space">
    <div class="book-hero">
      <div class="hero-copy">
        <span class="eyebrow">ACADEMIC BOOK FINDER</span>
        <h1>教材与电子书</h1>
        <p>中文教材优先，同时检索开放图书馆、学术书库与英文开放教材。</p>
      </div>
      <div class="hero-stat">
        <strong>{{ sources.length || 7 }}</strong>
        <span>个开放书源</span>
      </div>
    </div>

    <div class="search-deck">
      <div class="query-row">
        <el-input
          v-model="keyword"
          size="large"
          clearable
          placeholder="教材名称、作者或 ISBN，例如：高等数学 同济大学"
          @keyup.enter="runSearch(false)"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" size="large" :loading="loading" @click="runSearch(false)">
          搜索教材
        </el-button>
      </div>
      <div class="advanced-row">
        <el-input v-model="englishKeyword" clearable placeholder="英文关键词（可选，用于补充外文结果）" />
        <el-select v-model="selectedSource" placeholder="选择书源">
          <el-option label="全部书源" value="all" />
          <el-option v-for="source in sources" :key="source.id" :label="source.name" :value="source.id" />
        </el-select>
        <el-select v-model="selectedLanguage">
          <el-option label="中英文" value="all" />
          <el-option label="中文优先" value="zh" />
          <el-option label="仅外文" value="en" />
        </el-select>
        <el-select v-model="selectedFormat">
          <el-option label="全部格式" value="all" />
          <el-option label="PDF" value="pdf" />
          <el-option label="EPUB" value="epub" />
          <el-option label="TXT" value="txt" />
        </el-select>
        <el-checkbox v-model="onlyDownloadable">只看可下载</el-checkbox>
      </div>
    </div>

    <div v-if="Object.keys(sourceErrors).length" class="source-warning">
      <el-icon><Warning /></el-icon>
      <span>部分书源暂时不可用：</span>
      <span v-for="(message, source) in sourceErrors" :key="source" class="source-error"><b>{{ source }}</b>{{ message }}</span>
    </div>

    <div v-if="Object.keys(sourceStats).length" class="source-stats">
      <span v-for="(stat, source) in sourceStats" :key="source">
        {{ source }} <b>{{ stat.hits }}</b> 条 / <i>{{ stat.downloadable }}</i> 可下载
      </span>
    </div>

    <div v-loading="loading" class="result-area">
      <div v-if="items.length" class="result-head">
        <div>
          <strong>{{ visibleItems.length }}</strong> 条当前可见结果
          <span>· 已按 ISBN 或标题与第一作者去重</span>
        </div>
        <el-button text @click="void 0"><el-icon><FolderOpened /></el-icon> 打开下载目录</el-button>
      </div>

      <div class="book-grid">
        <article v-for="item in visibleItems" :key="item.id || item.detail_url" class="book-card">
          <div class="cover-wrap">
            <img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" loading="lazy" referrerpolicy="no-referrer" />
            <div v-else class="cover-empty"><el-icon><Reading /></el-icon><span>BOOK</span></div>
            <el-tag class="access-tag" :type="access(item).type" effect="dark" size="small">
              {{ access(item).label }}
            </el-tag>
          </div>

          <div class="book-body">
            <div class="source-line">{{ sourceLabel(item) }}</div>
            <h2>{{ item.title }}</h2>
            <p class="authors">{{ (item.authors || []).join('、') || '作者信息暂缺' }}</p>
            <div class="metadata">
              <span v-if="item.publisher">{{ item.publisher }}</span>
              <span v-if="item.published_year">{{ item.published_year }}</span>
              <span v-if="item.isbn13">ISBN {{ item.isbn13 }}</span>
              <span v-else-if="item.isbn10">ISBN {{ item.isbn10 }}</span>
            </div>
            <p v-if="item.description" class="description">{{ item.description }}</p>

            <div v-if="item.download_candidates?.length" class="download-list">
              <div v-for="candidate in item.download_candidates" :key="candidate.url" class="download-row">
                <div class="format-info">
                  <b>{{ candidate.format.toUpperCase() }}</b>
                  <span v-if="candidate.size">{{ (candidate.size / 1024 / 1024).toFixed(1) }} MB</span>
                </div>
                <el-button
                  size="small"
                  type="success"
                  plain
                  :loading="downloadStates[candidateKey(item, candidate)] && !['completed', 'failed'].includes(downloadStates[candidateKey(item, candidate)].status)"
                  @click="downloadBook(item, candidate)"
                >
                  安全下载
                </el-button>
              </div>
            </div>
            <div v-else class="no-file">当前来源未提供可验证的直接文件</div>

            <div class="card-actions">
              <el-button v-if="item.detail_url" text type="primary" @click="openExternal(item.detail_url)">
                查看来源 <el-icon><TopRight /></el-icon>
              </el-button>
              <span v-if="item.license" class="license" :title="item.license">开放许可</span>
            </div>
          </div>
        </article>
      </div>

      <el-empty v-if="!loading && !items.length" description="输入教材名称开始跨书源搜索">
        <template #image><el-icon class="empty-icon"><Collection /></el-icon></template>
      </el-empty>
      <div v-if="hasMore && items.length" class="load-more">
        <el-button :loading="loadingMore" @click="runSearch(true)">加载更多结果</el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.book-space { max-width: 1400px; margin: 0 auto; }
.book-hero { position: relative; display: flex; justify-content: space-between; align-items: flex-end; overflow: hidden; padding: 30px 34px; color: #eff6ff; border-radius: 18px 18px 0 0; background: radial-gradient(circle at 80% 10%, rgba(56, 189, 248, .3), transparent 28%), linear-gradient(125deg, #172554 0%, #1e3a8a 54%, #0f766e 120%); }
.book-hero::after { content: ''; position: absolute; right: 18%; bottom: -65px; width: 180px; height: 180px; border: 1px solid rgba(255,255,255,.15); transform: rotate(24deg); }
.hero-copy { position: relative; z-index: 1; }
.eyebrow { font: 600 11px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .2em; color: #7dd3fc; }
.book-hero h1 { margin: 8px 0 5px; font: 700 34px/1.15 Georgia, 'Noto Serif SC', serif; letter-spacing: .04em; }
.book-hero p { margin: 0; color: #bfdbfe; font-size: 14px; }
.hero-stat { position: relative; z-index: 1; display: grid; text-align: right; }
.hero-stat strong { font: 700 40px/1 Georgia, serif; color: #fef3c7; }
.hero-stat span { margin-top: 5px; color: #bae6fd; font-size: 12px; }
.search-deck { padding: 22px 26px; border: 1px solid var(--border); border-top: 0; border-radius: 0 0 18px 18px; background: var(--card); box-shadow: 0 14px 30px rgba(15, 23, 42, .08); }
.query-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; }
.advanced-row { display: grid; grid-template-columns: minmax(220px, 1fr) repeat(3, 150px) auto; gap: 10px; align-items: center; margin-top: 12px; }
.source-warning { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 16px 2px 0; padding: 10px 14px; border: 1px solid #fde68a; border-radius: 10px; background: #fffbeb; color: #92400e; font-size: 13px; }
.source-error { display: inline-flex; max-width: 100%; gap: 5px; padding: 3px 7px; border-radius: 6px; background: rgba(255,255,255,.55); font-size: 11px; }.source-error b { flex-shrink: 0; }
.source-stats { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }.source-stats span { padding: 5px 9px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-sub); background: var(--card); font-size: 11px; }.source-stats b { color: #2563eb; }.source-stats i { color: #047857; font-style: normal; }
.result-area { min-height: 340px; padding-top: 24px; }
.result-head { display: flex; align-items: center; justify-content: space-between; margin: 0 2px 14px; color: var(--text-sub); font-size: 13px; }
.result-head strong { color: var(--text); font-size: 20px; }
.book-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.book-card { display: grid; grid-template-columns: 142px minmax(0, 1fr); min-height: 260px; overflow: hidden; border: 1px solid var(--border); border-radius: 14px; background: var(--card); transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
.book-card:hover { transform: translateY(-2px); border-color: #93c5fd; box-shadow: 0 13px 30px rgba(15, 23, 42, .1); }
.cover-wrap { position: relative; min-height: 100%; background: linear-gradient(145deg, #dbeafe, #e2e8f0); }
.cover-wrap img { width: 100%; height: 100%; min-height: 260px; object-fit: cover; }
.cover-empty { display: grid; place-content: center; gap: 8px; width: 100%; height: 100%; min-height: 260px; text-align: center; color: #64748b; background: repeating-linear-gradient(135deg, rgba(255,255,255,.45) 0 8px, transparent 8px 16px); }
.cover-empty .el-icon { margin: auto; font-size: 38px; }
.cover-empty span { font: 700 11px ui-monospace, monospace; letter-spacing: .18em; }
.access-tag { position: absolute; left: 8px; top: 8px; }
.book-body { min-width: 0; padding: 17px 18px 13px; }
.source-line { overflow: hidden; color: #2563eb; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-overflow: ellipsis; white-space: nowrap; text-transform: uppercase; }
.book-body h2 { display: -webkit-box; overflow: hidden; margin: 7px 0 4px; color: var(--text); font: 700 20px/1.35 Georgia, 'Noto Serif SC', serif; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.authors { overflow: hidden; margin: 0; color: var(--text-sub); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.metadata { display: flex; flex-wrap: wrap; gap: 5px 10px; margin-top: 10px; color: var(--text-sub); font-size: 12px; }
.metadata span + span::before { content: '·'; margin-right: 10px; color: #94a3b8; }
.description { display: -webkit-box; overflow: hidden; margin: 10px 0 0; color: var(--text-sub); font-size: 12px; line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.download-list { display: grid; gap: 7px; margin-top: 12px; }
.download-row { display: grid; grid-template-columns: minmax(80px, auto) auto; align-items: center; gap: 4px 8px; padding: 7px 9px; border-radius: 8px; background: var(--card-soft); }
.format-info { display: flex; align-items: baseline; gap: 8px; font-size: 11px; color: var(--text-sub); }
.format-info b { color: #047857; font: 800 12px ui-monospace, monospace; }
.download-row .el-progress, .task-message { grid-column: 1 / -1; }
.task-message { overflow: hidden; color: var(--text-sub); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.no-file { margin-top: 12px; padding: 8px; border-radius: 7px; color: var(--text-sub); background: var(--card-soft); font-size: 12px; text-align: center; }
.card-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.license { color: #047857; font-size: 11px; }
.load-more { padding: 24px 0; text-align: center; }
.empty-icon { font-size: 72px; color: #93c5fd; }
.external-shelf { margin-top: 24px; padding: 22px; border: 1px solid var(--border); border-radius: 16px; background: var(--card); }.external-head { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 14px; }.external-head h2 { margin: 5px 0 0; font: 700 21px Georgia, 'Noto Serif SC', serif; }.external-head p { max-width: 560px; margin: 0; color: var(--text-sub); font-size: 12px; text-align: right; }.external-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 9px; }.external-grid button { display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 9px; padding: 12px; border: 1px solid var(--border); border-radius: 10px; color: var(--text); background: var(--card-soft); cursor: pointer; text-align: left; }.external-grid button:hover { border-color: #60a5fa; }.external-grid span { display: grid; min-width: 0; }.external-grid small { overflow: hidden; margin-top: 3px; color: var(--text-sub); text-overflow: ellipsis; white-space: nowrap; }

@media (max-width: 1000px) {
  .advanced-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .book-grid { grid-template-columns: 1fr; }
  .external-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
}
@media (max-width: 620px) {
  .book-hero { align-items: flex-start; padding: 24px 20px; }
  .book-hero h1 { font-size: 28px; }
  .hero-stat { display: none; }
  .search-deck { padding: 16px; }
  .query-row, .advanced-row { grid-template-columns: 1fr; }
  .book-card { grid-template-columns: 104px minmax(0, 1fr); min-height: 230px; }
  .cover-wrap img, .cover-empty { min-height: 230px; }
  .book-body { padding: 14px 12px 10px; }
  .book-body h2 { font-size: 17px; }
  .description { display: none; }
  .external-head { align-items: flex-start; flex-direction: column; }.external-head p { text-align: left; }.external-grid { grid-template-columns: 1fr; }
}
</style>
