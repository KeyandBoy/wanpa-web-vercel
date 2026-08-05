<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { isLocal } from '../api'
import {
  SOURCE_GROUPS, sourceMap, SIMPLE_GROUPS, NOVEL_SOURCES, SIMPLE_NOVEL_GROUPS,
  COMIC_GROUPS, COMIC_SOURCES, SIMPLE_COMIC_GROUPS, PLUS_SOURCES, LITE_SOURCES
} from '../sources'
import {
  canPickFolder,
  createBlobSink,
  createFolderSink,
  createMemorySink,
  downloadZip,
  passLayers,
  runCrawl,
  sanitizeName
} from '../crawl'
import MultiLayerFilter from './MultiLayerFilter.vue'
import { api } from '../api'
import { license } from '../license'

const isPlus = computed(() => license.version === 'plus')

const form = reactive({
  keyword: '',
  sites: ['bing'],
  customUrls: '',
  count: 20,
  minWidth: 0,
  minHeight: 0,
  workers: 4,
  noWatermark: false,
  layers: []
})

const mode = ref('image')
const viewMode = ref('detail')
const leftWidth = ref(420)
const cform = reactive({
  keyword: '',
  sources: ['wnacg'],
  count: 20,
  preview: 60,
  layers: []
})
const cResults = ref([])
const cSearching = ref(false)
const cPreview = ref(null)
const cPreviewLoading = ref(false)
const cPreviewImages = ref([])
const cWhole = reactive({ running: false, done: 0, total: 0 })
const cWholeController = ref(null)
const nform = reactive({
  keyword: '',
  sources: ['aaanovel'],
  count: 20,
  layers: []
})
const nResults = ref([])
const nSearching = ref(false)
const nReading = ref(null)
const nContent = ref('')
const nContentLoading = ref(false)
const nSaving = ref(false)
const nRunning = ref(false)
const nDone = ref(0)
const nTotal = ref(0)
const nSummary = ref('')
const nSummarizing = ref(false)

const running = ref(false)
const done = ref(false)
const stats = reactive({ downloaded: 0, dup: 0, failed: 0, total: 0 })
const images = ref([])
const logs = ref([])
const zipPercent = ref(0)
const zipping = ref(false)
const controller = ref(null)
const sinkType = ref(canPickFolder() ? 'folder' : isLocal() ? 'memory' : 'blob')
const folderName = ref('')
const sink = ref(null)
const taskId = ref('')
const zipReady = ref(false)

const banner = computed(() => {
  if (sinkType.value === 'folder')
    return 'Chrome/Edge 文件夹直存：图片将直接保存到你选择的文件夹'
  if (sinkType.value === 'blob')
    return '暂存云端(Blob)：完成后打包 ZIP 下载，下载后自动清理云端文件'
  return '图片暂存浏览器内存：完成后打包 ZIP 下载'
})

const percent = computed(() => {
  if (stats.total <= 0) return 0
  return Math.min(100, Math.round((stats.downloaded / stats.total) * 100))
})

const imageLogs = ref([])
const novelLogs = ref([])
function pushImageLog(msg) {
  imageLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
  if (imageLogs.value.length > 200) imageLogs.value.splice(0, imageLogs.value.length - 200)
}
function pushNovelLog(msg) {
  novelLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
  if (novelLogs.value.length > 200) novelLogs.value.splice(0, novelLogs.value.length - 200)
}

const comicLogs = ref([])
function pushComicLog(msg) {
  comicLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
  if (comicLogs.value.length > 200) comicLogs.value.splice(0, comicLogs.value.length - 200)
}

async function cSearch() {
  if (cSearching.value) return
  if (!cform.keyword.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  if (!cform.sources.length) {
    ElMessage.warning('请至少选择一个漫画源')
    return
  }
  cSearching.value = true
  cResults.value = []
  cPreview.value = null
  cPreviewImages.value = []
  try {
    const results = await Promise.all(
      cform.sources.map(async (src) => {
        try {
          const r = await api.comicSearch({ keyword: cform.keyword.trim(), source: src, count: cform.count })
          return r.items || []
        } catch (e) {
          pushComicLog(`${src} 搜索失败，已跳过: ${e.message}`)
          return []
        }
      })
    )
    const seen = new Set()
    cResults.value = results.flat().filter((it) => {
      if (seen.has(it.url)) return false
      seen.add(it.url)
      return true
    })
    if (cform.layers.length && cResults.value.length) {
      const before = cResults.value.length
      cResults.value = cResults.value.filter((it) => passLayers(it, cform.layers))
      pushComicLog(`多层筛选: ${before} → ${cResults.value.length} 本`)
    }
    pushComicLog(`漫画搜索: 共 ${cResults.value.length} 部`)
    if (!cResults.value.length) ElMessage.warning('没有搜索到漫画')
  } catch (e) {
    ElMessage.error(`搜索失败: ${e.message}`)
  } finally {
    cSearching.value = false
  }
}

function cClearResults() {
  cResults.value = []
  cPreview.value = null
  cPreviewImages.value = []
}

async function cPreviewComic(item) {
  if (cPreviewLoading.value) return
  cPreviewLoading.value = true
  cPreview.value = item
  cPreviewImages.value = []
  try {
    pushComicLog(`预览: ${(item.title || '').slice(0, 40)}...`)
    const r = await api.comicPages(item.url, cform.preview)
    cPreview.value.title = r.title || item.title
    cPreviewImages.value = r.images || []
    pushComicLog(`预览获取 ${cPreviewImages.value.length} 张图片`)
    if (!cPreviewImages.value.length) ElMessage.warning('未获取到图片')
  } catch (e) {
    ElMessage.error(`预览失败: ${e.message}`)
  } finally {
    cPreviewLoading.value = false
  }
}

async function cDownloadWhole(item) {
  if (cWhole.running) return
  cWhole.running = true
  cWhole.done = 0
  cWhole.total = 0
  cWholeController.value = new AbortController()
  const files = []
  try {
    pushComicLog(`开始下载: ${(item.title || '').slice(0, 40)}...`)
    const r = await api.comicPages(item.url)
    const imgs = r.images || []
    if (!imgs.length) throw new Error('未获取到图片')
    cWhole.total = imgs.length
    const title = sanitizeName(r.title || item.title || 'comic')
    const workers = 6
    let idx = 0
    let fail = 0
    const run = async () => {
      while (idx < imgs.length) {
        const i = idx++
        if (cWholeController.value?.signal.aborted) return
        try {
          const blob = await fetch(api.proxyUrl(imgs[i])).then((x) => {
            if (!x.ok) throw new Error('HTTP ' + x.status)
            return x.blob()
          })
          const ext = (imgs[i].split('?')[0].match(/\.(jpe?g|png|gif|webp)$/i) || [])[1] || 'jpg'
          files.push({ path: `${title}/${String(i + 1).padStart(3, '0')}.${ext}`, blob })
        } catch (e) {
          fail += 1
        }
        cWhole.done++
      }
    }
    await Promise.all(Array.from({ length: Math.min(workers, imgs.length) }, run))
    if (!files.length) throw new Error('所有图片下载失败')
    pushComicLog(`开始打包 ZIP: ${title} (${files.length} 张${fail ? `, ${fail} 张失败` : ''})`)
    await downloadZip(files, `${title}.zip`)
    pushComicLog(`漫画下载完成: ${title} (${files.length} 张${fail ? `, ${fail} 张失败` : ''})`)
    ElMessage.success('ZIP 打包已开始下载')
  } catch (e) {
    if (e.name !== 'AbortError') ElMessage.error(`漫画下载失败: ${e.message}`)
  } finally {
    cWhole.running = false
    cWhole.total = 0
    cWhole.done = 0
    cWholeController.value = null
  }
}

function cCancelWhole() {
  if (cWholeController.value) {
    cWholeController.value.abort()
    pushComicLog('已请求停止...')
  }
}

function resetState() {
  running.value = false
  done.value = false
  zipReady.value = false
  stats.downloaded = stats.dup = stats.failed = 0
  stats.total = form.count * form.sites.length
  images.value = []
  imageLogs.value = []
  zipPercent.value = 0
  folderName.value = ''
}

async function start() {
  if (running.value) return
  if (!form.keyword.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  if (!form.sites.length) {
    ElMessage.warning('请至少选择一个数据源')
    return
  }
  const blocked = form.sites.filter((s) => isSourcePlus(s))
  if (!isPlus.value && blocked.length) {
    ElMessage.warning('所选数据源包含 Plus 专属功能，请先开通 Plus')
    return
  }
  resetState()
  running.value = true
  controller.value = new AbortController()
  taskId.value = crypto.randomUUID().slice(0, 12)

  let s
  if (sinkType.value === 'folder') {
    s = createFolderSink()
    try {
      const dir = await s.init()
      folderName.value = dir.name
    } catch (e) {
      running.value = false
      ElMessage.info('已取消选择文件夹')
      return
    }
    try {
      await s.prepare(form.sites.map((src) => `${form.keyword.trim()}/图片/${src}`))
    } catch (e) {
      running.value = false
      ElMessage.error(`文件夹写入授权失败: ${e.message}`)
      return
    }
  } else if (sinkType.value === 'blob') {
    s = createBlobSink(taskId.value)
  } else {
    s = createMemorySink()
  }
  sink.value = s

  try {
    await runCrawl({
      keyword: form.keyword.trim(),
      sources: form.sites,
      count: form.count,
      minWidth: form.minWidth,
      minHeight: form.minHeight,
      noWatermark: form.noWatermark,
      workers: form.workers,
      customUrls: form.customUrls,
      layers: form.layers,
      sink: s,
      signal: controller.value.signal,
      onProgress: (p) => {
        stats.downloaded = p.downloaded
        stats.dup = p.dup
        stats.failed = p.failed
        stats.total = p.total
        if (p.type === 'image' && p.previewUrl) {
          images.value.push({ url: p.previewUrl, path: p.path })
        }
      },
      onLog: pushImageLog
    })
    done.value = true
    zipReady.value = sinkType.value !== 'folder'
    pushImageLog(
      sinkType.value === 'folder'
        ? `全部完成，图片已保存到文件夹: ${folderName.value}`
        : '全部完成，可以打包 ZIP 下载了'
    )
  } catch (e) {
    if (e.name !== 'AbortError') {
      pushImageLog(`任务失败: ${e.message}`)
      ElMessage.error(`任务失败: ${e.message}`)
    }
  } finally {
    running.value = false
    controller.value = null
  }
}

function cancel() {
  if (controller.value) {
    controller.value.abort()
    pushImageLog('已请求停止...')
  }
}

async function buildFiles() {
  if (sinkType.value === 'memory') {
    return sink.value.getFiles()
  }
  const files = []
  for (const img of images.value) {
    const blob = await fetch(img.url).then((r) => r.blob())
    files.push({ path: img.path, blob })
  }
  return files
}

async function downloadZipNow() {
  if (zipping.value) return
  zipping.value = true
  zipPercent.value = 0
  try {
    const files = await buildFiles()
    if (!files.length) {
      ElMessage.warning('没有可打包的文件')
      return
    }
    await downloadZip(files, `${form.keyword.trim()}_图片.zip`, (p) => {
      zipPercent.value = Math.round(p)
    })
    ElMessage.success('ZIP 下载已开始')
    if (sinkType.value === 'blob') {
      await cleanupBlob()
    }
  } catch (e) {
    ElMessage.error(`打包失败: ${e.message}`)
  } finally {
    zipping.value = false
    zipPercent.value = 0
  }
}

async function cleanupBlob() {
  if (sinkType.value !== 'blob') return
  try {
    const r = await sink.value.cleanup()
    pushImageLog(`已清理云端临时文件 ${r.deleted} 个`)
    ElMessage.success(`已清理云端临时文件 ${r.deleted} 个`)
  } catch (e) {
    ElMessage.error(`清理失败: ${e.message}`)
  }
}

function groupChecked(g, sites) {
  return g.sources.every((s) => sites.includes(s))
}

function groupIndeterminate(g, sites) {
  const c = g.sources.filter((s) => sites.includes(s)).length
  return c > 0 && c < g.sources.length
}

function toggleGroup(g, sites, setSites) {
  if (groupChecked(g, sites)) {
    setSites(sites.filter((s) => !g.sources.includes(s)))
  } else {
    setSites([...new Set([...sites, ...g.sources])])
  }
}

// ---- 版本分流 ----
function visibleImageGroups() {
  return SOURCE_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((s) => isPlus.value || s.tier === 'lite'),
  })).filter((g) => g.items.length)
}
function visibleSimpleGroups() {
  return SIMPLE_GROUPS.filter((g) => isPlus.value || g.tier === 'lite')
}
function visibleNovelSources() {
  return NOVEL_SOURCES.filter((s) => isPlus.value || s.tier === 'lite')
}
function visibleSimpleNovelGroups() {
  return SIMPLE_NOVEL_GROUPS.filter((g) => isPlus.value || g.tier === 'lite')
}
function isSourcePlus(id) {
  return PLUS_SOURCES.has(id)
}
function ensurePlusAccess(source) {
  if (isPlus.value) return true
  if (isSourcePlus(source)) {
    ElMessage.warning('该功能为 Plus 专属，请点击右上角「Lite」开通')
    return false
  }
  return true
}

function startLeftDrag(e) {
  e.preventDefault()
  const startX = e.clientX
  const startW = leftWidth.value
  const move = (ev) => {
    leftWidth.value = Math.min(720, Math.max(300, startW + (ev.clientX - startX)))
  }
  const up = () => {
    document.removeEventListener('mousemove', move)
    document.removeEventListener('mouseup', up)
    document.body.style.cursor = ''
  }
  document.body.style.cursor = 'ew-resize'
  document.addEventListener('mousemove', move)
  document.addEventListener('mouseup', up)
}

async function nSearch() {
  if (nSearching.value) return
  if (!nform.keyword.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  if (!nform.sources.length) {
    ElMessage.warning('请至少选择一个小说源')
    return
  }
  if (!isPlus.value && nform.sources.some((s) => isSourcePlus(s))) {
    ElMessage.warning('所选小说源为 Plus 专属，请先开通 Plus')
    return
  }
  nSearching.value = true
  nResults.value = []
  nReading.value = null
  nContent.value = ''
  try {
    const results = await Promise.all(
      nform.sources.map(async (src) => {
        try {
          const r = await api.novelSearch({ keyword: nform.keyword.trim(), source: src, page: 1 })
          return r.items || []
        } catch (e) {
          pushNovelLog(`${src} 搜索失败，已跳过: ${e.message}`)
          return []
        }
      })
    )
    const seen = new Set()
    nResults.value = results.flat().filter((it) => {
      if (seen.has(it.url)) return false
      seen.add(it.url)
      return true
    })
    if (nform.layers.length && nResults.value.length) {
      const before = nResults.value.length
      nResults.value = nResults.value.filter((it) => passLayers(it, nform.layers))
      pushNovelLog(`多层筛选: ${before} → ${nResults.value.length} 篇`)
    }
    pushNovelLog(`小说搜索: 共 ${nResults.value.length} 篇`)
    if (!nResults.value.length) ElMessage.warning('没有搜索到小说')
  } catch (e) {
    ElMessage.error(`搜索失败: ${e.message}`)
  } finally {
    nSearching.value = false
  }
}

function nClearResults() {
  nResults.value = []
  nReading.value = null
  nContent.value = ''
}

async function nRead(item) {
  if (nContentLoading.value) return
  nContentLoading.value = true
  nReading.value = item
  nContent.value = ''
  try {
    const r = await api.novelContent(item.url)
    nContent.value = r.content || ''
    if (!nContent.value) ElMessage.warning('未提取到正文')
  } catch (e) {
    ElMessage.error(`阅读失败: ${e.message}`)
  } finally {
    nContentLoading.value = false
  }
}

const nWhole = reactive({ running: false, done: 0, total: 0 })
const nWholeController = ref(null)

function nIsBiquga(item) {
  return (item.source || '').toLowerCase() === 'biquga'
}

async function nDownloadWhole(item) {
  if (nWhole.running) return
  nWhole.running = true
  nWhole.done = 0
  nWhole.total = 0
  nWholeController.value = new AbortController()
  let dirName = ''
  const sink = createFolderSink()
  try {
    const dir = await sink.init()
    dirName = dir.name
  } catch (e) {
    ElMessage.info('已取消选择文件夹')
    nWhole.running = false
    return
  }
  try {
    await sink.prepare([`${nform.keyword.trim() || 'novel'}/小说`])
  } catch (e) {
    ElMessage.error(`文件夹写入授权失败: ${e.message}`)
    nWhole.running = false
    return
  }
  try {
    pushNovelLog(`获取目录: ${item.title.slice(0, 40)}...`)
    const r = await api.novelChapters(item.url)
    const chapters = r.chapters || []
    if (!chapters.length) throw new Error('目录为空')
    nWhole.total = chapters.length
    pushNovelLog(`共 ${chapters.length} 章，开始整本爬取...`)
    const parts = [item.title]
    const workers = 6
    let idx = 0
    let fail = 0
    const run = async () => {
      while (idx < chapters.length) {
        const i = idx++
        if (nWholeController.value?.signal.aborted) return
        const ch = chapters[i]
        try {
          const c = await api.novelContent(ch.url)
          if (c.content) {
            parts.push(`\n\n${ch.title}\n\n${c.content}`)
          } else {
            fail += 1
          }
        } catch (e) {
          fail += 1
        }
        nWhole.done++
      }
    }
    await Promise.all(Array.from({ length: Math.min(workers, chapters.length) }, run))
    const text = parts.join('')
    const title = sanitizeName(item.title)
    const path = `${nform.keyword.trim() || 'novel'}/小说/biquga/${title}.txt`
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    await sink.save({ path, blob })
    pushNovelLog(`整本完成: ${title}.txt (${chapters.length} 章${fail ? `, ${fail} 章失败` : ''})`)
    ElMessage.success(`整本已保存到 ${dirName}`)
  } catch (e) {
    if (e.name !== 'AbortError') ElMessage.error(`整本下载失败: ${e.message}`)
  } finally {
    nWhole.running = false
    nWhole.total = 0
    nWhole.done = 0
    nWholeController.value = null
  }
}

async function nSummarize() {
  if (nSummarizing.value || !nContent.value) return
  nSummarizing.value = true
  nSummary.value = ''
  try {
    const r = await api.dsSummarize(nContent.value.slice(0, 3000))
    nSummary.value = r.summary || ''
  } catch (e) {
    ElMessage.error(`摘要失败: ${e.message}`)
  } finally {
    nSummarizing.value = false
  }
}

async function nSaveTxt() {
  if (nSaving.value || !nReading.value || !nContent.value) return
  nSaving.value = true
  try {
    const sink = createFolderSink()
    let dir
    try {
      dir = await sink.init()
    } catch (e) {
      ElMessage.info('已取消选择文件夹')
      return
    }
    try {
      await sink.prepare([`${nform.keyword.trim() || 'novel'}/小说`])
    } catch (e) {
      ElMessage.error(`文件夹写入授权失败: ${e.message}`)
      return
    }
    const title = sanitizeName(nReading.value.title)
    const path = `${nform.keyword.trim() || 'novel'}/小说/${nReading.value.source}/${title}.txt`
    const blob = new Blob([nContent.value], { type: 'text/plain;charset=utf-8' })
    await sink.save({ path, blob })
    pushNovelLog(`已保存: ${path}`)
    ElMessage.success(`已保存到: ${dir.name}/${path}`)
  } catch (e) {
    ElMessage.error(`保存失败: ${e.message}`)
  } finally {
    nSaving.value = false
  }
}

function nIsEnglishSource(src) {
  const s = NOVEL_SOURCES.find((x) => x.id === src)
  return s ? s.tag === '英文' : false
}

async function nStartDownload() {
  if (nRunning.value || !nResults.value.length) return
  nRunning.value = true
  let dirName = ''
  try {
    const sink = createFolderSink()
    let dir
    try {
      dir = await sink.init()
      dirName = dir.name
    } catch (e) {
      ElMessage.info('已取消选择文件夹')
      return
    }
    try {
      await sink.prepare([`${nform.keyword.trim() || 'novel'}/小说`])
    } catch (e) {
      ElMessage.error(`文件夹写入授权失败: ${e.message}`)
      return
    }
    const targets = nResults.value.slice(0, nform.count)
    nTotal.value = targets.length
    nDone.value = 0
    pushNovelLog(`开始爬取 ${targets.length} 篇小说...`)
    for (let i = 0; i < targets.length; i++) {
      const it = targets[i]
      try {
        const translate = nIsEnglishSource(it.source)
        const r = await api.novelContent(it.url, translate)
        if (!r.content) throw new Error('正文为空')
        let content = r.content
        const title = sanitizeName(it.title)
        const path = `${nform.keyword.trim() || 'novel'}/小说/${it.source}/${title}.txt`
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
        await sink.save({ path, blob })
        pushNovelLog(`[${i + 1}/${targets.length}] 已保存: ${title}.txt`)
      } catch (e) {
        pushNovelLog(`[${i + 1}/${targets.length}] 保存失败: ${it.title} → ${e.message}`)
      }
      nDone.value++
    }
    ElMessage.success(`完成，已保存到 ${dirName}`)
  } catch (e) {
    ElMessage.error(`爬取失败: ${e.message}`)
  } finally {
    nRunning.value = false
    nTotal.value = 0
    nDone.value = 0
  }
}

onBeforeUnmount(() => {
  controller.value?.abort()
  cWholeController.value?.abort()
})
</script>

<template>
  <div class="workspace">
    <div class="left" :style="{ width: leftWidth + 'px' }">
      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <span>爬取设置</span>
            <span class="head-right">
              <el-radio-group v-model="viewMode" size="small">
                <el-radio-button value="detail">详细</el-radio-button>
                <el-radio-button value="simple">简单</el-radio-button>
              </el-radio-group>
              <el-radio-group v-model="mode" size="small">
                <el-radio-button value="image">图片</el-radio-button>
                <el-radio-button value="novel">小说</el-radio-button>
                <el-radio-button value="comic">漫画</el-radio-button>
              </el-radio-group>
            </span>
          </div>
        </template>

        <el-form v-if="mode === 'image'" label-width="80px" label-position="left">
          <el-form-item label="关键词">
            <el-input v-model="form.keyword" clearable />
          </el-form-item>
          <el-form-item label="多层筛选">
            <MultiLayerFilter v-model="form.layers" />
          </el-form-item>
          <el-form-item label="数据源">
            <div v-if="viewMode === 'simple'" class="simple-groups">
              <div v-for="g in visibleSimpleGroups()" :key="g.id" class="simple-group">
                <el-tooltip :open-delay="800" placement="top" effect="light">
                  <template #content>
                    <div class="tip">
                      <div class="tip-title">
                        {{ g.label }}
                        <el-tag size="small" :type="g.adult ? 'danger' : 'info'" effect="plain">{{ g.tag }}</el-tag>
                        <el-tag v-if="g.tier === 'plus'" size="small" type="warning" effect="plain">Plus</el-tag>
                      </div>
                      <div class="tip-desc">{{ g.desc }}</div>
                    </div>
                  </template>
                  <el-checkbox
                    :model-value="groupChecked(g, form.sites)"
                    :indeterminate="groupIndeterminate(g, form.sites)"
                    @change="toggleGroup(g, form.sites, (v) => (form.sites = v))"
                  >
                    <span :class="{ adult: g.adult }">{{ g.label }}（{{ g.sources.length }}个站）</span>
                  </el-checkbox>
                </el-tooltip>
              </div>
            </div>
            <div v-else class="source-groups">
              <div v-for="group in visibleImageGroups()" :key="group.name" class="source-group">
                <div class="group-name">{{ group.name }}</div>
                <el-checkbox-group v-model="form.sites" class="group-checks">
                  <span v-for="s in group.items" :key="s.id" class="src-item">
                    <el-tooltip :open-delay="800" placement="top" effect="light">
                      <template #content>
                        <div class="tip">
                          <div class="tip-title">
                            {{ s.label }}
                            <el-tag size="small" :type="s.adult ? 'danger' : 'info'" effect="plain">
                              {{ s.tag }}
                            </el-tag>
                            <el-tag v-if="s.tier === 'plus'" size="small" type="warning" effect="plain">Plus</el-tag>
                          </div>
                          <div class="tip-desc">{{ s.desc }}</div>
                        </div>
                      </template>
                      <el-checkbox :value="s.id">
                        <span :class="{ adult: s.adult }">{{ s.label }}</span>
                      </el-checkbox>
                    </el-tooltip>
                  </span>
                </el-checkbox-group>
              </div>
            </div>
          </el-form-item>
          <el-form-item v-if="form.sites.includes('custom')" label="网址">
            <el-input
              v-model="form.customUrls"
              type="textarea"
              :rows="3"
            />
          </el-form-item>
          <el-form-item label="数量">
            <el-slider v-model="form.count" :min="1" :max="200" show-input />
          </el-form-item>
          <el-form-item label="最小宽高">
            <el-input-number v-model="form.minWidth" :min="0" :step="100" controls-position="right" />
            <span class="x">x</span>
            <el-input-number v-model="form.minHeight" :min="0" :step="100" controls-position="right" />
            <span class="hint">0=不限</span>
          </el-form-item>
          <el-form-item label="并发数">
            <el-slider v-model="form.workers" :min="1" :max="8" show-input />
          </el-form-item>
          <el-form-item label="过滤">
            <el-switch v-model="form.noWatermark" />
            <span class="hint">关闭疑似水印 URL 过滤</span>
          </el-form-item>
        </el-form>

        <el-form v-if="mode === 'novel'" label-width="80px" label-position="left">
          <el-form-item label="关键词">
            <el-input v-model="nform.keyword" clearable />
          </el-form-item>
          <el-form-item label="多层筛选">
            <MultiLayerFilter v-model="nform.layers" />
          </el-form-item>
          <el-form-item label="数据源">
            <div class="source-groups">
              <div v-if="viewMode === 'simple'" class="simple-groups">
                <div v-for="g in visibleSimpleNovelGroups()" :key="g.id" class="simple-group">
                  <el-tooltip :open-delay="800" placement="top" effect="light">
                    <template #content>
                      <div class="tip">
                        <div class="tip-title">
                          {{ g.label }}
                          <el-tag size="small" type="info" effect="plain">{{ g.tag }}</el-tag>
                        </div>
                        <div class="tip-desc">{{ g.desc }}</div>
                      </div>
                    </template>
                    <el-checkbox
                      :model-value="groupChecked(g, nform.sources)"
                      :indeterminate="groupIndeterminate(g, nform.sources)"
                      @change="toggleGroup(g, nform.sources, (v) => (nform.sources = v))"
                    >
                      {{ g.label }}（{{ g.sources.length }}个站）
                    </el-checkbox>
                  </el-tooltip>
                </div>
              </div>
              <el-checkbox-group v-else v-model="nform.sources" class="group-checks">
                <span v-for="s in visibleNovelSources()" :key="s.id" class="src-item">
                  <el-tooltip :open-delay="800" placement="top" effect="light">
                    <template #content>
                      <div class="tip">
                        <div class="tip-title">
                          {{ s.label }}
                          <el-tag size="small" type="info" effect="plain">{{ s.tag }}</el-tag>
                        </div>
                        <div class="tip-desc">{{ s.desc }}</div>
                      </div>
                    </template>
                    <el-checkbox :value="s.id">{{ s.label }}</el-checkbox>
                  </el-tooltip>
                </span>
              </el-checkbox-group>
            </div>
          </el-form-item>
          <el-form-item label="数量">
            <el-slider v-model="nform.count" :min="1" :max="200" show-input />
          </el-form-item>
          <div class="actions">
            <el-button type="primary" :loading="nSearching" @click="nSearch">搜索</el-button>
            <el-button type="success" :loading="nRunning" :disabled="!nResults.length" @click="nStartDownload">
              开始爬取
            </el-button>
          </div>
          <div v-if="nResults.length" class="novel-res">
            <div class="novel-res-head">
              <span>候选 {{ nResults.length }} 篇</span>
              <el-button size="small" link @click="nClearResults">清空</el-button>
            </div>
            <div class="novel-res-list">
              <div
                v-for="it in nResults"
                :key="it.url"
                class="novel-res-item"
                :class="{ active: nReading && nReading.url === it.url }"
                @click="nRead(it)"
              >
                <span class="novel-res-title" :title="it.title">{{ it.title }}</span>
                <el-tag size="small" type="info" effect="plain">{{ it.source }}</el-tag>
                <el-button
                  v-if="nIsBiquga(it)"
                  size="small"
                  link
                  type="primary"
                  :loading="nWhole.running"
                  @click.stop="nDownloadWhole(it)"
                >
                  整本下载
                </el-button>
              </div>
            </div>
          </div>
        </el-form>

        <el-form v-if="mode === 'comic'" label-width="80px" label-position="left">
          <el-form-item label="关键词">
            <el-input v-model="cform.keyword" clearable />
          </el-form-item>
          <el-form-item label="多层筛选">
            <MultiLayerFilter v-model="cform.layers" />
          </el-form-item>
          <el-form-item label="数据源">
            <div class="source-groups">
              <div v-if="viewMode === 'simple'" class="simple-groups">
                <div v-for="g in SIMPLE_COMIC_GROUPS" :key="g.id" class="simple-group">
                  <el-tooltip :open-delay="800" placement="top" effect="light">
                    <template #content>
                      <div class="tip">
                        <div class="tip-title">
                          {{ g.label }}
                          <el-tag size="small" type="warning" effect="plain">Plus</el-tag>
                        </div>
                        <div class="tip-desc">{{ g.desc }}</div>
                      </div>
                    </template>
                    <el-checkbox
                      :model-value="groupChecked(g, cform.sources)"
                      :indeterminate="groupIndeterminate(g, cform.sources)"
                      @change="toggleGroup(g, cform.sources, (v) => (cform.sources = v))"
                    >
                      {{ g.label }}（{{ g.sources.length }}个站）
                    </el-checkbox>
                  </el-tooltip>
                </div>
              </div>
              <div v-else class="source-groups">
                <div v-for="group in COMIC_GROUPS" :key="group.name" class="source-group">
                  <div class="group-name">{{ group.name }}</div>
                  <el-checkbox-group v-model="cform.sources" class="group-checks">
                    <span v-for="s in group.items" :key="s.id" class="src-item">
                      <el-tooltip :open-delay="800" placement="top" effect="light">
                        <template #content>
                          <div class="tip">
                            <div class="tip-title">
                              {{ s.label }}
                              <el-tag size="small" type="warning" effect="plain">Plus</el-tag>
                            </div>
                            <div class="tip-desc">{{ s.desc }}</div>
                          </div>
                        </template>
                        <el-checkbox :value="s.id">{{ s.label }}</el-checkbox>
                      </el-tooltip>
                    </span>
                  </el-checkbox-group>
                </div>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="数量">
            <el-slider v-model="cform.count" :min="1" :max="200" show-input />
          </el-form-item>
          <el-form-item label="预览张数">
            <el-input-number v-model="cform.preview" :min="10" :max="200" controls-position="right" />
          </el-form-item>
          <div class="actions">
            <el-button type="primary" :loading="cSearching" @click="cSearch">搜索</el-button>
          </div>
          <div v-if="cResults.length" class="novel-res">
            <div class="novel-res-head">
              <span>候选 {{ cResults.length }} 部（点击预览，右侧可整本下载）</span>
              <el-button size="small" link @click="cClearResults">清空</el-button>
            </div>
            <div class="novel-res-list">
              <div
                v-for="it in cResults"
                :key="it.url"
                class="novel-res-item comic-res-item"
                :class="{ active: cPreview && cPreview.url === it.url }"
                @click="cPreviewComic(it)"
              >
                <img v-if="it.cover" class="comic-cover" :src="it.cover" alt="" loading="lazy" />
                <span class="novel-res-title" :title="it.title">{{ it.title }}</span>
                <el-tag size="small" type="info" effect="plain">{{ it.source }}</el-tag>
                <el-tag v-if="it.is_cn" size="small" type="success" effect="plain">汉化</el-tag>
              </div>
            </div>
          </div>
        </el-form>

        <div class="actions">
          <el-button
            v-if="mode === 'image'"
            type="primary"
            size="large"
            :loading="running"
            :disabled="running"
            @click="start"
          >
            {{ sinkType === 'folder' ? '选择文件夹并开始爬取' : '开始爬取' }}
          </el-button>
          <el-button v-if="running && mode === 'image'" size="large" @click="cancel">停止</el-button>
        </div>
        <el-alert v-if="mode === 'image'" class="banner" :title="banner" type="info" :closable="false" />
      </el-card>
      <div class="left-handle" title="拖动调整宽度" @mousedown="startLeftDrag">
        <span class="handle-grip"></span>
      </div>
    </div>

    <div class="right">
      <el-card v-if="mode === 'image'" shadow="never">
        <template #header>
          爬取进度
          <span v-if="folderName" class="folder-hint">→ {{ folderName }}</span>
        </template>
        <el-progress :percentage="percent" :stroke-width="18">
          <span class="progress-text">{{ percent }}% / {{ stats.total }} 张</span>
        </el-progress>
        <div class="stats">
          已下载 <b>{{ stats.downloaded }}</b> 张
          <span class="dim">| 去重 {{ stats.dup }} | 失败 {{ stats.failed }}</span>
        </div>
        <div v-if="zipReady" class="zip-bar">
          <el-button
            type="success"
            :loading="zipping"
            :disabled="zipping"
            @click="downloadZipNow"
          >
            打包下载 ZIP
          </el-button>
          <el-button v-if="sinkType === 'blob'" plain @click="cleanupBlob">清理云端临时文件</el-button>
          <span v-if="zipping" class="dim">打包中 {{ zipPercent }}%</span>
        </div>
        <div v-if="imageLogs.length" class="logs">
          <div v-for="(l, i) in imageLogs" :key="i" class="log-line">{{ l }}</div>
        </div>
      </el-card>

      <el-card v-if="mode === 'novel'" shadow="never">
        <template #header>
          爬取进度
          <span v-if="nTotal" class="dim">({{ nDone }} / {{ nTotal }})</span>
          <span v-else-if="nWhole.total" class="dim">整本 ({{ nWhole.done }} / {{ nWhole.total }})</span>
        </template>
        <el-progress
          v-if="nTotal"
          :percentage="Math.round((nDone / nTotal) * 100)"
          :stroke-width="18"
        >
          <span class="progress-text">{{ nDone }} / {{ nTotal }} 篇</span>
        </el-progress>
        <el-progress
          v-else-if="nWhole.total"
          :percentage="Math.round((nWhole.done / nWhole.total) * 100)"
          :stroke-width="18"
        >
          <span class="progress-text">{{ nWhole.done }} / {{ nWhole.total }} 章</span>
        </el-progress>
        <el-empty v-if="!novelLogs.length" description="还没有小说日志" :image-size="60" />
        <div v-else class="logs nlogs">
          <div v-for="(l, i) in novelLogs" :key="i" class="log-line">{{ l }}</div>
        </div>
      </el-card>

      <el-card v-if="mode === 'novel'" shadow="never" class="player-card">
        <template #header>
          阅读
          <span v-if="nReading" class="dim">{{ nReading.title }}</span>
        </template>
        <div v-if="nContentLoading" class="preview-loading">加载正文中...</div>
        <template v-else-if="nContent">
          <div v-if="nSummary" class="novel-summary">{{ nSummary }}</div>
          <div class="novel-content">{{ nContent }}</div>
          <div class="novel-actions">
            <el-button type="primary" :loading="nSaving" @click="nSaveTxt">下载为 txt</el-button>
            <el-button :loading="nSummarizing" @click="nSummarize">AI 摘要</el-button>
          </div>
        </template>
        <el-empty v-else description="点击左侧小说开始阅读" :image-size="60" />
      </el-card>

      <el-card v-if="mode === 'comic'" shadow="never">
        <template #header>
          漫画下载
          <span v-if="cWhole.total" class="dim">({{ cWhole.done }} / {{ cWhole.total }})</span>
        </template>
        <el-progress
          v-if="cWhole.total"
          :percentage="Math.round((cWhole.done / cWhole.total) * 100)"
          :stroke-width="18"
        >
          <span class="progress-text">{{ cWhole.done }} / {{ cWhole.total }} 张</span>
        </el-progress>
        <div v-if="cPreview && !cWhole.running" class="comic-dl-bar">
          <el-button type="success" @click="cDownloadWhole(cPreview)">整本打包 ZIP 下载</el-button>
          <span class="dim">将整本漫画打包为 ZIP 下载（多页将逐张拉取）</span>
        </div>
        <el-button v-if="cWhole.running" @click="cCancelWhole">停止</el-button>
        <el-empty v-if="!comicLogs.length" description="还没有漫画日志" :image-size="60" />
        <div v-else class="logs nlogs">
          <div v-for="(l, i) in comicLogs" :key="i" class="log-line">{{ l }}</div>
        </div>
      </el-card>

      <el-card v-if="mode === 'comic'" shadow="never" class="player-card">
        <template #header>
          漫画预览
          <span v-if="cPreview" class="dim">{{ cPreview.title }}</span>
          <el-button v-if="cPreview" class="comic-preview-close" size="small" link @click="cPreview = null">
            关闭
          </el-button>
        </template>
        <div v-if="cPreviewLoading" class="preview-loading">加载预览中...</div>
        <template v-else-if="cPreviewImages.length">
          <div class="comic-wall">
            <el-image
              v-for="(u, i) in cPreviewImages"
              :key="u"
              class="comic-wall-item"
              :src="api.proxyUrl(u)"
              :preview-src-list="cPreviewImages.map((x) => api.proxyUrl(x))"
              :initial-index="i"
              fit="cover"
            />
          </div>
        </template>
        <el-empty v-else description="点击左侧漫画预览" :image-size="60" />
      </el-card>

      <el-card shadow="never" v-if="images.length">
        <template #header>已下载预览 ({{ images.length }})</template>
        <div class="gallery">
          <el-image
            v-for="(img, i) in images"
            :key="img.path"
            class="thumb"
            :src="img.url"
            :preview-src-list="images.map((x) => x.url)"
            :initial-index="i"
            fit="cover"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.workspace {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.left {
  width: 420px;
  flex-shrink: 0;
  position: relative;
  transition: width 0.05s;
}
.left-handle {
  position: absolute;
  top: 0;
  right: -6px;
  width: 12px;
  height: 100%;
  cursor: ew-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
}
.player-handle {
  height: 14px;
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
  border: 1px solid #e4e7ed;
  border-top: none;
  border-radius: 0 0 6px 6px;
}
.player-box {
  position: relative;
}
.novel-res {
  margin-top: 12px;
  border-top: 1px solid #ebeef5;
  padding-top: 10px;
}
.novel-res-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.novel-res-list {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}
.novel-res-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 10px;
  cursor: pointer;
  border-bottom: 1px solid #f0f2f5;
  transition: background 0.15s;
}
.novel-res-item:hover {
  background: #f5f7fa;
}
.novel-res-item.active {
  background: #ecf5ff;
}
.novel-res-item:last-child {
  border-bottom: none;
}
.novel-res-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.comic-res-item {
  gap: 8px;
}
.comic-dl-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.comic-cover {
  width: 34px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 4px;
  border: 1px solid var(--border);
  object-fit: cover;
}
.comic-wall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 8px;
  max-height: 60vh;
  overflow-y: auto;
}
.comic-wall-item {
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 4px;
  cursor: pointer;
}
.comic-big {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.comic-big-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.comic-big-page {
  font-size: 13px;
  color: var(--wp-text-2, #909399);
}
.comic-big-toolbar .spacer {
  flex: 1;
}
.comic-big-img {
  width: 100%;
  max-height: 75vh;
}
.comic-preview-close {
  float: right;
  margin-top: -2px;
}
.novel-content {
  max-height: 480px;
  overflow-y: auto;
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.9;
  color: #303133;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 14px 16px;
}
.novel-actions {
  margin-top: 10px;
}
.handle-grip {
  display: block;
  width: 32px;
  height: 3px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 2px;
}
.head-right {
  display: flex;
  gap: 8px;
  align-items: center;
}
.simple-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.right {
  flex: 1;
  min-width: 0;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.x {
  margin: 0 8px;
  color: #909399;
}
.hint {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}
.actions {
  margin: 8px 0;
}
.banner {
  margin-top: 12px;
}
.folder-hint {
  margin-left: 8px;
  color: #67c23a;
  font-size: 13px;
}
.stats {
  margin-top: 10px;
  font-size: 14px;
}
.progress-text {
  font-size: 13px;
  color: #606266;
}
.dim {
  color: #909399;
  font-size: 13px;
}
.zip-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.logs {
  margin-top: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 8px 12px;
  max-height: 180px;
  overflow-y: auto;
  font-size: 12px;
  color: #606266;
}
.log-line {
  line-height: 1.7;
  font-family: Consolas, monospace;
}
.gallery {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.source-groups {
  width: 100%;
}
.source-group {
  margin-bottom: 10px;
}
.source-group:last-child {
  margin-bottom: 0;
}
.group-name {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.group-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}
.src-item {
  display: inline-flex;
}
.adult {
  color: #f56c6c;
  font-weight: 600;
}
.tip {
  max-width: 320px;
}
.tip-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.tip-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
  white-space: pre-line;
}
.thumb {
  width: 120px;
  height: 120px;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}
.video-tabs {
  width: 100%;
}
.v-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.v-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.v-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}
.v-label {
  width: 44px;
  flex-shrink: 0;
  color: #606266;
  font-size: 14px;
}
.vresults {
  margin-top: 12px;
  border-top: 1px dashed #e4e7ed;
  padding-top: 10px;
}
.vres-head {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}
.vres-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 6px 10px;
  margin-bottom: 10px;
}
.vres-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  border-bottom: 1px solid #f0f2f5;
}
.vres-item:last-child {
  border-bottom: none;
}
.vres-title {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vres-dur {
  color: #909399;
  font-size: 12px;
  flex-shrink: 0;
}
.link-info {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
  color: #606266;
  line-height: 1.8;
  word-break: break-all;
}
.link-tip {
  color: #909399;
  font-size: 12px;
  cursor: help;
}
.vtasks {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.vtask {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 10px;
}
.vtask-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.vtask-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.vtask-status {
  flex-shrink: 0;
  font-size: 12px;
  color: #909399;
}
.vtask-status.saved {
  color: #67c23a;
}
.vtask-status.error {
  color: #f56c6c;
}
.vtask-status.canceled {
  color: #909399;
}
.vtask-err {
  margin-top: 4px;
  font-size: 12px;
  color: #f56c6c;
  word-break: break-all;
}
.vtask-sum {
  font-size: 13px;
  color: #606266;
}
.preview-loading {
  text-align: center;
  color: #909399;
  padding: 30px 0;
}
.preview-info {
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
  margin-bottom: 10px;
  word-break: break-all;
}
.preview-note {
  color: #e6a23c;
}
.preview-video {
  width: 100%;
  max-height: 400px;
  background: #000;
  border-radius: 6px;
}
.player-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
  border-radius: 6px;
}
.player-wrap {
  width: 100%;
  position: relative;
  background: #000;
  border-radius: 6px;
  overflow: hidden;
}
.player-card {
  margin-top: 16px;
}
.vres-item {
  cursor: pointer;
  transition: background 0.15s;
}
.vres-item:hover {
  background: #f5f7fa;
}
</style>
