<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { isLocal } from '../api'
import {
  SOURCE_GROUPS, sourceMap, VIDEO_SOURCES, videoSourceMap, SIMPLE_GROUPS,
  NOVEL_SOURCES, SIMPLE_NOVEL_GROUPS, SIMPLE_VIDEO_GROUPS,
  COMIC_GROUPS, COMIC_SOURCES, SIMPLE_COMIC_GROUPS, PLUS_SOURCES, LITE_SOURCES
} from '../sources'
import {
  canPickFolder,
  createBlobSink,
  createFolderSink,
  createMemorySink,
  downloadZip,
  durationPass,
  formatDur,
  formatReport,
  nowTime,
  passLayers,
  runCrawl,
  sanitizeName
} from '../crawl'
import MultiLayerFilter from './MultiLayerFilter.vue'
import { api } from '../api'
import { license } from '../license'

const props = defineProps({ mode: { type: String, default: 'image' } })

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

const mode = computed(() => props.mode)
const viewMode = ref('detail')
const heroTitle = computed(
  () => ({ image: '图片资源', video: '视频资源', novel: '小说资源', comic: '漫画资源' })[mode.value] || '资源'
)
const heroDesc = computed(
  () =>
    ({
      image: '跨多个图片来源检索、筛选并批量保存资源。',
      video: '跨多个视频源检索、解析并在本页在线播放。',
      novel: '检索小说内容，在线阅读并保存个人学习资料。',
      comic: '检索漫画作品，预览页面并保存开放内容。'
    })[mode.value] || ''
)
const heroMark = computed(
  () => ({ image: 'IMG', video: 'VID', novel: 'TXT', comic: 'COMIC' })[mode.value] || ''
)
const navTabs = []
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
  sources: ['biquga'],
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
const nCategories = ref([])
const nCategoryMode = ref(false)
const nCategoryType = ref('')
const nCategoryLoading = ref(false)
const nCategoryPage = ref(1)
const nReaderSettings = reactive({
  fontSize: parseInt(localStorage.getItem('novel_fontSize') || '18', 10),
  lineHeight: parseFloat(localStorage.getItem('novel_lineHeight') || '2.0'),
  bgMode: localStorage.getItem('novel_bgMode') || 'sepia' // day | sepia | night
})
const nChapters = ref([])
const nChaptersLoading = ref(false)
const nCurrentChapterIndex = ref(0)
const nChapterContent = ref('')

// ---- 视频：搜索 / 解析 / 在线播放 ----
const vform = reactive({
  keyword: '',
  sources: ['bing'],
  count: 10,
  duration: 'any',
  layers: []
})
const vTab = ref('search')
const vResults = ref([])
const vSearching = ref(false)
const vFilteredOut = ref(0)
const videoLogs = ref([])
function pushVideoLog(msg) {
  videoLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
  if (videoLogs.value.length > 200) videoLogs.value.splice(0, videoLogs.value.length - 200)
}

const linkUrl = ref('')
const linkTitle = ref('')
const linkInfo = ref(null)
const linkResolving = ref(false)
const linkMode = ref('auto')
const linkResults = ref([])

// 播放器：DASH 站音视频分离时用两个元素同步（服务端无 ffmpeg 合不了流）
const playerSrc = ref('')
const playerSig = ref('')
const playerAudioSrc = ref('')
const playerAudioSig = ref('')
const playerTitle = ref('')
const playerLoading = ref(false)
const playerItemUrl = ref('')
const playerSession = ref(0)
const playerReady = ref(false)
const playerHeight = ref(360)
const playerHint = ref('')
const videoRef = ref(null)
const audioRef = ref(null)
let hlsInstance = null
let HlsModule = null

async function loadHls() {
  if (!HlsModule) HlsModule = await import('hls.js')
  return HlsModule.default
}

function destroyHls() {
  if (hlsInstance) {
    hlsInstance.destroy()
    hlsInstance = null
  }
}

// 用户意图：视频该不该有声。暂停/切换都要清掉，否则迟到的 play() 会把声音又带出来
let audioWantPlay = false

function resetPlayer() {
  destroyHls()
  playerSrc.value = ''
  playerSig.value = ''
  playerAudioSrc.value = ''
  playerAudioSig.value = ''
  playerReady.value = false
  playerHint.value = ''
  audioWantPlay = false
}

// 双流同步：视频元素是主控（用户操作它），音频元素静默跟随
let audioSyncing = false
function safeSetTime(el, t) {
  if (!el) return
  try {
    audioSyncing = true
    el.currentTime = t
  } catch (_) {
    /* 元素尚未就绪 */
  } finally {
    audioSyncing = false
  }
}
function playAudio() {
  if (!audioWantPlay) return
  const a = audioRef.value
  if (a && playerAudioSrc.value && a.paused) {
    // play() 是异步的：等它真的起来后若期间已被暂停，必须补一次 pause，
    // 否则暂停操作会被这次迟到的 play 覆盖掉。
    a.play()
      .then(() => {
        if (!audioWantPlay) a.pause()
      })
      .catch(() => pushVideoLog('音频未自动出声，点击视频画面即可出声'))
  }
}
function onVideoPlay() {
  audioWantPlay = true
}
function onVideoPlaying() {
  // 视频真正渲染出画面了才放音频，避免画面还没出来声音先响
  playAudio()
}
function onVideoPause() {
  audioWantPlay = false
  const a = audioRef.value
  if (a) a.pause()
}
function onVideoSeek() {
  const a = audioRef.value
  const v = videoRef.value
  if (a && v && playerAudioSrc.value) safeSetTime(a, v.currentTime)
}
function onVideoTime() {
  const a = audioRef.value
  const v = videoRef.value
  if (!a || !v || audioSyncing || !playerAudioSrc.value) return
  if (Math.abs(a.currentTime - v.currentTime) > 0.4) safeSetTime(a, v.currentTime)
}
function onPlayerClick() {
  // 用户手势里补一次，绕过浏览器的有声自动播放策略。
  // 必须先看视频当前是不是在播：点暂停按钮的 click 也会冒泡到这里，
  // 不判断的话刚被暂停的音频会被重新播起来。
  const v = videoRef.value
  if (v && v.paused) return
  playAudio()
}
function onAudioError() {
  pushVideoLog('音频流加载失败，当前可能无声')
}

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
  if (!isPlus.value) {
    ElMessage.warning('漫画板块为 Plus 专属，请点击右上角「Lite」开通')
    return
  }
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
          const etype = e.errorType || ''
          const typeLabel = etype === 'timeout' ? '(超时)' : etype === 'connection_error' ? '(连接失败)' : etype === 'source_blocked' ? '(源站拦截)' : etype === 'ssl_error' ? '(SSL错误)' : ''
          pushComicLog(`${src} 搜索失败${typeLabel}，已跳过: ${e.message}`)
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
  if (!isPlus.value) {
    ElMessage.warning('漫画板块为 Plus 专属，请点击右上角「Lite」开通')
    return
  }
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
    if (window.innerWidth <= 991) {
      await nextTick()
      document.querySelector('.player-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
}

async function cDownloadWhole(item) {
  if (!isPlus.value) {
    ElMessage.warning('漫画板块为 Plus 专属，请点击右上角「Lite」开通')
    return
  }
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
      await s.prepare([`${form.keyword.trim()}/图片`])
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
  if (sinkType.value === 'blob' && sink.value.getReportFiles) {
    files.push(...sink.value.getReportFiles())
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

function onModeChange(v) {
  if (v === 'comic' && !isPlus.value) {
    ElMessage.warning('漫画板块为 Plus 专属，请点击右上角「Lite」开通')
    return
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

// ---- 视频：分组与版本分流 ----
const VIDEO_GROUPS = computed(() => [
  {
    name: '国内',
    items: ['bing', 'bilibili', 'acfun', 'youku', 'mgtv']
      .map((id) => videoSourceMap[id])
      .filter(Boolean)
  },
  {
    name: '国外通用',
    items: ['yahoo', 'youtube', 'twitter'].map((id) => videoSourceMap[id]).filter(Boolean)
  },
  {
    name: 'porn成人',
    items: ['pornhub', 'thothub', 'xnxx', 'xvideos', 'xhamster', 'doll', 'cg51']
      .map((id) => videoSourceMap[id])
      .filter(Boolean)
  },
  { name: '随机', items: ['xjj'].map((id) => videoSourceMap[id]).filter(Boolean) }
])

function visibleVideoGroups() {
  return VIDEO_GROUPS.value
    .map((g) => ({ ...g, items: g.items.filter((s) => isPlus.value || s.tier === 'lite') }))
    .filter((g) => g.items.length)
}
function visibleSimpleVideoGroups() {
  return SIMPLE_VIDEO_GROUPS.filter((g) => isPlus.value || g.tier === 'lite')
}

function stageLabel(s) {
  switch (s) {
    case 'direct':
      return '直链'
    case 'ytdlp':
      return 'yt-dlp'
    case 'sniff':
      return '服务端嗅探'
    case 'site':
      return '站点特判'
    case 'douyin':
      return '抖音'
    case 'audio':
      return '音频流'
    default:
      return s || '-'
  }
}

function candKindLabel(c) {
  if (c.ext === 'm3u8') return 'HLS'
  if (c.kind === 'audio') return '音频'
  if (c.ext && c.ext !== 'unknown') return c.ext.toUpperCase()
  return stageLabel(c.kind) || '媒体'
}

function openExternal(url) {
  window.open(url, '_blank', 'noopener')
}

function startPlayerDrag(e) {
  e.preventDefault()
  const startY = e.clientY
  const startH = playerHeight.value
  const move = (ev) => {
    playerHeight.value = Math.min(800, Math.max(160, startH + (ev.clientY - startY)))
  }
  const up = () => {
    document.removeEventListener('mousemove', move)
    document.removeEventListener('mouseup', up)
    document.body.style.cursor = ''
  }
  document.body.style.cursor = 'ns-resize'
  document.addEventListener('mousemove', move)
  document.addEventListener('mouseup', up)
}

async function vSearch() {
  if (vSearching.value) return
  if (!vform.keyword.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  if (!vform.sources.length) {
    ElMessage.warning('请至少选择一个数据源')
    return
  }
  const searchable = vform.sources.filter((s) => s !== 'link')
  if (!searchable.length) {
    ElMessage.warning('「链接解析」不能用关键词搜索，请切换到「链接解析」标签页粘贴链接')
    return
  }
  if (!isPlus.value && searchable.some((s) => isSourcePlus(s))) {
    ElMessage.warning('所选视频源为 Plus 专属，请先开通 Plus')
    return
  }
  vSearching.value = true
  vResults.value = []
  vFilteredOut.value = 0
  try {
    const kw = vform.keyword.trim()
    const results = await Promise.all(
      searchable.map(async (src) => {
        try {
          const r = await api.videoSearch({ keyword: kw, source: src, count: vform.count })
          return r.items || []
        } catch (e) {
          pushVideoLog(`搜索失败 ${src}: ${e.message}`)
          return []
        }
      })
    )
    const seen = new Set()
    const all = results.flat().filter((i) => {
      if (seen.has(i.url)) return false
      seen.add(i.url)
      return true
    })
    let passed = all.filter((i) => durationPass(i.duration, vform.duration))
    vFilteredOut.value = all.length - passed.length
    if (vform.layers.length && passed.length) {
      const before = passed.length
      passed = passed.filter((it) => passLayers(it, vform.layers))
      pushVideoLog(`多层筛选: ${before} → ${passed.length} 条`)
    }
    vResults.value = passed
    if (!passed.length) {
      pushVideoLog('筛选后无匹配结果')
      ElMessage.warning('没有符合筛选条件的视频，试试调整数据源或筛选规则')
      return
    }
    pushVideoLog(
      `视频搜索(${searchable.join('+')}): ${all.length} 条候选` +
        (vFilteredOut.value ? `(按时长过滤 ${vFilteredOut.value} 条)` : '')
    )
  } catch (e) {
    ElMessage.error(`搜索失败: ${e.message}`)
    pushVideoLog(`视频搜索失败: ${e.message}`)
  } finally {
    vSearching.value = false
  }
}

function vRowClick(item) {
  vPreview(item)
}

async function vPreview(item) {
  if (playerLoading.value) return
  playerLoading.value = true
  const mySession = ++playerSession.value
  resetPlayer()
  playerTitle.value = item.title
  playerItemUrl.value = item.url || ''
  pushVideoLog(`开始解析: ${item.title}`)
  try {
    const info = await api.videoResolve(item.url)
    if (mySession !== playerSession.value) return
    const direct = info.url
    if (!direct) {
      playerTitle.value = `${item.title} · 解析失败`
      pushVideoLog(`解析失败: 未拿到播放地址`)
      return
    }
    if (info.is_hls ?? /\.m3u8(\?|$)/i.test(direct)) {
      // HLS 交给 hls.js（分片与子播放列表由 rewrite_playlist 逐个加签名）
      const videoEl = videoRef.value
      if (!videoEl) throw new Error('播放器未就绪')
      destroyHls()
      const Hls = await loadHls()
      if (mySession !== playerSession.value) return
      if (Hls.isSupported()) {
        const hls = new Hls({ maxBufferLength: 60, enableWorker: true })
        hlsInstance = hls
        hls.loadSource(api.hlsPlaylistUrl(direct, info.sig))
        hls.attachMedia(videoEl)
        hls.on(Hls.Events.ERROR, (_e, data) => {
          if (!data.fatal) return
          pushVideoLog(`播放错误: ${data.type} ${data.details}`)
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad()
          else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError()
          else {
            playerTitle.value = `${item.title} · 播放出错`
            destroyHls()
          }
        })
      } else if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
        videoEl.src = api.hlsPlaylistUrl(direct, info.sig)
      } else {
        throw new Error('当前浏览器不支持 HLS 播放')
      }
      playerReady.value = true
      playerTitle.value = `${item.title} · ${info.format || 'HLS'}`
      pushVideoLog(`预览就绪: ${item.title} (${info.format || 'HLS'}) hls.js`)
      return
    }

    // DASH 站音视频分离：视频流 + 音频流双元素同步播放
    playerSrc.value = api.videoPreviewUrl(direct, info.sig)
    if (info.audio_url && info.audio_url !== direct) {
      playerAudioSrc.value = api.videoPreviewUrl(info.audio_url, info.audio_sig)
      playerHint.value = '双流播放（音视频分离，已自动同步）'
      pushVideoLog(`音视频分离: 视频 ${info.format || ''} + 音频 ${info.audio_format || ''}`)
    } else {
      playerHint.value = ''
    }
    playerReady.value = true
    playerTitle.value = `${item.title} · ${info.format || ''}`
    pushVideoLog(`预览就绪: ${info.title || item.title} (${info.format || ''})`)
  } catch (e) {
    if (mySession !== playerSession.value) return
    playerTitle.value = `${item.title} · 解析失败`
    pushVideoLog(`解析失败: ${e.message}`)
    ElMessage.error(`解析失败: ${e.message}`)
  } finally {
    if (mySession === playerSession.value) playerLoading.value = false
  }
}

function splitLinkLines() {
  return (linkUrl.value || '')
    .split(/[\r\n]+/)
    .map((s) => s.trim())
    .filter((s) => /^https?:\/\//i.test(s))
    .slice(0, 10)
}

async function resolveOneLine(raw) {
  const isDouyin = /douyin|iesdouyin|v\.douyin/i.test(raw)
  if (isDouyin) {
    const d = await api.douyinParse(raw)
    if (d.type === 'album') {
      form.customUrls = (d.image_urls || []).join('\n')
      ElMessage.success('抖音图集已填入图片自定义网址，请到图片模块爬取')
      return { input: raw, type: 'album', title: d.title || '抖音图集', image_urls: d.image_urls || [], candidates: [], error: '' }
    }
    return {
      input: raw,
      type: 'video',
      title: d.title || '抖音视频',
      format: 'mp4',
      stage: 'douyin',
      source_url: raw,
      candidates: [{ url: d.video_url, ext: 'mp4', kind: 'direct', quality: '', label: '无水印 mp4', from: 'douyin' }],
      error: ''
    }
  }
  try {
    const info = await api.videoResolve(raw, linkMode.value)
    const cands =
      info.candidates && info.candidates.length
        ? info.candidates
        : [
            {
              url: info.url,
              ext: info.is_hls ? 'm3u8' : 'mp4',
              kind: info.stage || 'direct',
              quality: '',
              label: info.format || '',
              from: info.stage || ''
            }
          ]
    return {
      input: raw,
      type: 'video',
      title: info.title || raw,
      format: info.format,
      duration: info.duration,
      stage: info.stage || '',
      source_url: info.source_url || raw,
      sig: info.sig,
      audio_url: info.audio_url,
      audio_sig: info.audio_sig,
      candidates: cands,
      error: ''
    }
  } catch (e) {
    return { input: raw, type: 'video', title: raw, format: '', candidates: [], error: e.message }
  }
}

async function vResolveLink() {
  const lines = splitLinkLines()
  if (!lines.length) {
    ElMessage.warning('请粘贴至少一条 http(s) 链接（每行一条）')
    return
  }
  linkResolving.value = true
  linkResults.value = []
  linkInfo.value = null
  try {
    const out = []
    for (const line of lines) out.push(await resolveOneLine(line))
    linkResults.value = out
    const ok = out.filter((r) => !r.error && r.candidates.length)
    const first = ok[0]
    if (first) {
      linkInfo.value = {
        title: first.title,
        format: first.format,
        duration: first.duration,
        stage: first.stage,
        candidates: first.candidates
      }
      if (!linkTitle.value.trim() && first.title) linkTitle.value = first.title
      pushVideoLog(`解析成功: ${first.title} (${first.format || '未知格式'}) · ${stageLabel(first.stage)}`)
    }
    pushVideoLog(
      `解析完成: ${ok.length}/${out.length} 成功` + (lines.length > 1 ? `（共 ${lines.length} 行）` : '')
    )
    if (!first && out.length) ElMessage.warning(`全部解析失败: ${out[0].error || '无可用地址'}`)
  } finally {
    linkResolving.value = false
  }
}

// 直接播放链接解析出来的候选（签名由 resolve 时附带）
async function vPlayCandidate(res, cand) {
  if (!cand || !cand.url) return
  if (cand.kind === 'audio') {
    ElMessage.info('该候选是音频流，播放视频流即可自动带上声音')
    return
  }
  const fake = {
    title: linkTitle.value.trim() || res.title || '链接解析',
    url: res.input || res.source_url,
    source: 'link'
  }
  // 候选已是直链，跳过二次解析直接播
  if (playerLoading.value) return
  playerLoading.value = true
  const mySession = ++playerSession.value
  resetPlayer()
  playerTitle.value = fake.title
  playerItemUrl.value = fake.url
  try {
    const isHls = cand.ext === 'm3u8'
    // play_url 是服务端按「候选自己的 URL」签好的完整地址；
    // res.sig 签的是 info.url，只在候选就是首条时才对得上
    const playUrl = cand.play_url || (isHls ? api.hlsPlaylistUrl(cand.url, res.sig) : api.videoPreviewUrl(cand.url, res.sig))
    if (isHls) {
      const videoEl = videoRef.value
      if (!videoEl) throw new Error('播放器未就绪')
      const Hls = await loadHls()
      if (mySession !== playerSession.value) return
      if (Hls.isSupported()) {
        const hls = new Hls({ maxBufferLength: 60, enableWorker: true })
        hlsInstance = hls
        hls.loadSource(playUrl)
        hls.attachMedia(videoEl)
      } else {
        videoEl.src = playUrl
      }
      playerReady.value = true
      playerTitle.value = `${fake.title} · HLS`
      pushVideoLog(`链接播放: HLS ${fake.title}`)
      return
    }
    playerSrc.value = playUrl
    if (res.audio_url && res.audio_url !== cand.url) {
      playerAudioSrc.value = api.videoPreviewUrl(res.audio_url, res.audio_sig)
      playerHint.value = '双流播放（音视频分离，已自动同步）'
    } else {
      playerHint.value = ''
    }
    playerReady.value = true
    playerTitle.value = `${fake.title} · ${cand.label || cand.ext || ''}`
    pushVideoLog(`链接播放: ${fake.title} (${cand.label || cand.ext || ''})`)
  } catch (e) {
    if (mySession !== playerSession.value) return
    pushVideoLog(`链接播放失败: ${e.message}`)
    ElMessage.error(`播放失败: ${e.message}`)
  } finally {
    if (mySession === playerSession.value) playerLoading.value = false
  }
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
          const etype = e.errorType || ''
          const typeLabel = etype === 'timeout' ? '(超时)' : etype === 'connection_error' ? '(连接失败)' : etype === 'source_blocked' ? '(源站拦截)' : etype === 'ssl_error' ? '(SSL错误)' : ''
          pushNovelLog(`${src} 搜索失败${typeLabel}，已跳过: ${e.message}`)
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
  nChapters.value = []
  nCurrentChapterIndex.value = 0
  nChapterContent.value = ''
}

function nCloseReader() {
  nReading.value = null
  nContent.value = ''
  nSummary.value = ''
  nChapters.value = []
  nCurrentChapterIndex.value = 0
  nChapterContent.value = ''
}

// ---- 天天看小说分类浏览 ----
async function nToggleCategoryMode() {
  if (nCategoryMode.value) {
    nCategoryMode.value = false
    nCategoryType.value = ''
    return
  }
  try {
    const r = await api.novelCategories()
    nCategories.value = r.categories || []
    nCategoryMode.value = true
    nCategoryPage.value = 1
    if (nCategories.value.length) {
      await nBrowseCategory(nCategories.value[0].type)
    }
  } catch (e) {
    ElMessage.error(`分类加载失败: ${e.message}`)
  }
}

async function nBrowseCategory(type) {
  nCategoryType.value = type
  nCategoryPage.value = 1
  nCategoryLoading.value = true
  nResults.value = []
  try {
    const r = await api.novelCategory({ type, page: 1 })
    nResults.value = r.items || []
    pushNovelLog(`天天看小说分类[${type}]: 共 ${nResults.value.length} 篇`)
  } catch (e) {
    ElMessage.error(`分类浏览失败: ${e.message}`)
  } finally {
    nCategoryLoading.value = false
  }
}

async function nBrowseCategoryMore() {
  nCategoryLoading.value = true
  try {
    const next = nCategoryPage.value + 1
    const r = await api.novelCategory({ type: nCategoryType.value, page: next })
    const items = r.items || []
    if (!items.length) {
      ElMessage.info('没有更多了')
    } else {
      nCategoryPage.value = next
      const seen = new Set(nResults.value.map((it) => it.url))
      nResults.value.push(...items.filter((it) => !seen.has(it.url)))
    }
  } catch (e) {
    ElMessage.error(`加载更多失败: ${e.message}`)
  } finally {
    nCategoryLoading.value = false
  }
}

async function nRead(item) {
  if (nContentLoading.value) return
  nContentLoading.value = true
  nReading.value = item
  nContent.value = ''
  nChapters.value = []
  nCurrentChapterIndex.value = 0
  nChapterContent.value = ''
  try {
    // 先尝试获取目录
    nChaptersLoading.value = true
    try {
      const chr = await api.novelChapters(item.url)
      if (chr.chapters && chr.chapters.length > 0) {
        nChapters.value = chr.chapters
        // 自动打开第一章
        await nLoadChapter(0)
      } else {
        // 无目录，直接读取当前URL内容
        const r = await api.novelContent(item.url)
        nContent.value = r.content || ''
        nChapterContent.value = ''
        if (!nContent.value) ElMessage.warning('未提取到正文')
      }
    } catch {
      // 目录获取失败，直接读取内容
      const r = await api.novelContent(item.url)
      nContent.value = r.content || ''
      nChapterContent.value = ''
      if (!nContent.value) ElMessage.warning('未提取到正文')
    }
  } catch (e) {
    ElMessage.error(`阅读失败: ${e.message}`)
  } finally {
    nContentLoading.value = false
    nChaptersLoading.value = false
    if (window.innerWidth <= 991) {
      await nextTick()
      document.querySelector('.player-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
}

async function nLoadChapter(index) {
  if (index < 0 || index >= nChapters.value.length) return
  nCurrentChapterIndex.value = index
  nContentLoading.value = true
  nContent.value = ''
  nChapterContent.value = ''
  try {
    const ch = nChapters.value[index]
    const r = await api.novelContent(ch.url)
    nChapterContent.value = r.content || ''
    nContent.value = nChapterContent.value
    if (!nContent.value) ElMessage.warning('未提取到正文')
    // 复位阅读容器滚动条
    const el = document.querySelector('.novel-reader-body')
    if (el) el.scrollTop = 0
  } catch (e) {
    ElMessage.error(`章节加载失败: ${e.message}`)
  } finally {
    nContentLoading.value = false
  }
}

function nPrevChapter() {
  if (nCurrentChapterIndex.value > 0) {
    nLoadChapter(nCurrentChapterIndex.value - 1)
  }
}

function nNextChapter() {
  if (nCurrentChapterIndex.value < nChapters.value.length - 1) {
    nLoadChapter(nCurrentChapterIndex.value + 1)
  }
}

function nSetBgMode(mode) {
  nReaderSettings.bgMode = mode
  localStorage.setItem('novel_bgMode', mode)
}

function nSetFontSize(size) {
  nReaderSettings.fontSize = size
  localStorage.setItem('novel_fontSize', String(size))
}

function nSetLineHeight(v) {
  nReaderSettings.lineHeight = v
  localStorage.setItem('novel_lineHeight', String(v))
}

const nReaderBgClass = computed(() => {
  return `reader-bg-${nReaderSettings.bgMode}`
})

const nCurrentChapterName = computed(() => {
  if (nChapters.value.length > 0 && nChapters.value[nCurrentChapterIndex.value]) {
    return nChapters.value[nCurrentChapterIndex.value].title
  }
  return ''
})

const nHasChapters = computed(() => nChapters.value.length > 1)


const nWhole = reactive({ running: false, done: 0, total: 0 })
const nWholeController = ref(null)

function nIsBiquga(item) {
  const s = (item.source || '').toLowerCase()
  return s === 'biquga' || s === 'bqgnovels' || s === 'txt800' || s === 'alicesw'
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
    const failRec = []
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
            failRec.push({ time: nowTime(), source: item.source, url: ch.url, title: ch.title, error: '内容为空' })
          }
        } catch (e) {
          fail += 1
          failRec.push({ time: nowTime(), source: item.source, url: ch.url, title: ch.title, error: e.message })
        }
        nWhole.done++
      }
    }
    await Promise.all(Array.from({ length: Math.min(workers, chapters.length) }, run))
    const text = parts.join('')
    const title = sanitizeName(item.title)
    const path = `${nform.keyword.trim() || 'novel'}/小说/${title}.txt`
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    await sink.save({ path, blob })
    const txt = formatReport(nform.keyword.trim() || 'novel', '小说', [{
      time: nowTime(),
      source: item.source,
      url: item.url,
      title: item.title,
      size: blob.size,
      path,
    }], failRec)
    await sink.appendReport?.(`${nform.keyword.trim() || 'novel'}/小说/下载信息.txt`, txt)
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
    const path = `${nform.keyword.trim() || 'novel'}/小说/${title}.txt`
    const blob = new Blob([nContent.value], { type: 'text/plain;charset=utf-8' })
    await sink.save({ path, blob })
    const txt = formatReport(nform.keyword.trim() || 'novel', '小说', [{
      time: nowTime(),
      source: nReading.value.source,
      url: nReading.value.url,
      title: nReading.value.title,
      size: blob.size,
      path,
    }], [])
    await sink.appendReport?.(`${nform.keyword.trim() || 'novel'}/小说/下载信息.txt`, txt)
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
    const okRec = []
    const failRec = []
    pushNovelLog(`开始爬取 ${targets.length} 篇小说...`)
    for (let i = 0; i < targets.length; i++) {
      const it = targets[i]
      try {
        const translate = nIsEnglishSource(it.source)
        const r = await api.novelContent(it.url, translate)
        if (!r.content) throw new Error('正文为空')
        let content = r.content
        const title = sanitizeName(it.title)
        const path = `${nform.keyword.trim() || 'novel'}/小说/${title}.txt`
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
        await sink.save({ path, blob })
        okRec.push({ time: nowTime(), source: it.source, url: it.url, title: it.title, size: blob.size, path })
        pushNovelLog(`[${i + 1}/${targets.length}] 已保存: ${title}.txt`)
      } catch (e) {
        failRec.push({ time: nowTime(), source: it.source, url: it.url, title: it.title, error: e.message })
        pushNovelLog(`[${i + 1}/${targets.length}] 保存失败: ${it.title} → ${e.message}`)
      }
      nDone.value++
    }
    const txt = formatReport(nform.keyword.trim() || 'novel', '小说', okRec, failRec)
    await sink.appendReport?.(`${nform.keyword.trim() || 'novel'}/小说/下载信息.txt`, txt)
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
  playerSession.value++
  destroyHls()
})
</script>

<template>
  <div class="workspace">
    <header class="crawl-hero">
      <div>
        <span class="eyebrow">MULTI-SOURCE RESOURCE FINDER</span>
        <h1>{{ heroTitle }}</h1>
        <p>{{ heroDesc }}</p>
      </div>
      <div class="hero-mark"><span>{{ heroMark }}</span></div>
    </header>
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
            <div class="novel-kw-row">
              <el-input v-model="nform.keyword" clearable />
              <el-button
                size="small"
                :type="nCategoryMode ? 'warning' : 'default'"
                @click="nToggleCategoryMode"
                :loading="nCategoryLoading"
              >
                {{ nCategoryMode ? '退出分类' : '分类浏览' }}
              </el-button>
            </div>
            <div v-if="nCategoryMode && nCategories.length" class="novel-cat-bar">
              <span class="novel-cat-label">内容分类</span>
              <el-select v-model="nCategoryType" size="small" style="width: 120px" @change="nBrowseCategory">
                <el-option v-for="c in nCategories" :key="c.type || 'latest'" :label="c.name" :value="c.type" />
              </el-select>
              <el-button size="small" text @click="nBrowseCategoryMore">下一页</el-button>
            </div>
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
                <span class="novel-res-title" :title="(it.title_zh && it.title_zh !== it.title) ? it.title_zh + ' (' + it.title + ')' : it.title">
                  {{ it.title_zh || it.title }}
                  <span v-if="it.title_zh && it.title_zh !== it.title" class="res-title-orig">{{ it.title }}</span>
                </span>
                <el-tag size="small" type="info" effect="plain">{{ it.source }}</el-tag>
                <el-tag v-if="it.is_cn" size="small" type="success" effect="plain">汉化</el-tag>
              </div>
            </div>
          </div>
        </el-form>

        <el-form v-if="mode === 'video'" label-width="80px" label-position="left" class="video-form">
          <el-tabs v-model="vTab" class="video-tabs">
            <el-tab-pane label="搜索" name="search">
              <el-form-item label="关键词">
                <el-input v-model="vform.keyword" clearable placeholder="视频关键词（随机源忽略关键词）" @keyup.enter="vSearch" />
              </el-form-item>
              <el-form-item label="数据源">
                <div class="source-groups">
                  <div v-if="viewMode === 'simple'" class="simple-groups">
                    <div v-for="g in visibleSimpleVideoGroups()" :key="g.id" class="simple-group">
                      <el-tooltip :open-delay="800" placement="top" effect="light">
                        <template #content>
                          <div class="tip">
                            <div class="tip-title">
                              {{ g.label }}
                              <el-tag size="small" :type="g.tier === 'plus' ? 'warning' : 'success'" effect="plain">
                                {{ g.tier === 'plus' ? 'Plus' : 'Lite' }}
                              </el-tag>
                            </div>
                            <div class="tip-desc">{{ g.desc }}</div>
                          </div>
                        </template>
                        <el-checkbox
                          :model-value="groupChecked(g, vform.sources)"
                          :indeterminate="groupIndeterminate(g, vform.sources)"
                          @change="toggleGroup(g, vform.sources, (v) => (vform.sources = v))"
                        >
                          {{ g.label }}（{{ g.sources.length }}个站）
                        </el-checkbox>
                      </el-tooltip>
                    </div>
                  </div>
                  <div v-else class="source-groups">
                    <div v-for="group in visibleVideoGroups()" :key="group.name" class="source-group">
                      <div class="group-name">{{ group.name }}</div>
                      <el-checkbox-group v-model="vform.sources" class="group-checks">
                        <span v-for="s in group.items" :key="s.id" class="src-item">
                          <el-tooltip :open-delay="800" placement="top" effect="light">
                            <template #content>
                              <div class="tip">
                                <div class="tip-title">
                                  {{ s.label }}
                                  <el-tag
                                    size="small"
                                    :type="s.tier === 'plus' ? 'warning' : 'success'"
                                    effect="plain"
                                  >
                                    {{ s.tier === 'plus' ? 'Plus' : 'Lite' }}
                                  </el-tag>
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
                </div>
              </el-form-item>
              <el-form-item label="数量">
                <el-slider v-model="vform.count" :min="1" :max="30" show-input />
              </el-form-item>
              <el-form-item label="时长">
                <el-radio-group v-model="vform.duration">
                  <el-radio value="any">不限</el-radio>
                  <el-radio value="short">短 (&lt;10分)</el-radio>
                  <el-radio value="medium">中 (10-60分)</el-radio>
                  <el-radio value="long">长 (&gt;60分)</el-radio>
                </el-radio-group>
                <span v-if="vform.sources.includes('pornhub') && vform.duration !== 'any'" class="hint">
                  Pornhub 结果无时长，需选「不限」
                </span>
              </el-form-item>
              <el-form-item v-if="viewMode === 'detail'" label="多层筛选">
                <MultiLayerFilter v-model="vform.layers" />
              </el-form-item>
              <div class="actions">
                <el-button type="primary" :loading="vSearching" @click="vSearch">搜索</el-button>
                <span v-if="vFilteredOut" class="hint">按时长过滤 {{ vFilteredOut }} 条</span>
              </div>
              <div v-if="vResults.length" class="novel-res vresults">
                <div class="novel-res-head">
                  <span>候选 {{ vResults.length }} 条（点击任意一行即可右侧播放）</span>
                  <el-button size="small" link @click="vResults = []">清空</el-button>
                </div>
                <div class="novel-res-list">
                  <div
                    v-for="item in vResults"
                    :key="item.url"
                    class="novel-res-item vres-item"
                    :class="{ active: playerItemUrl === item.url }"
                    @click="vRowClick(item)"
                  >
                    <el-tooltip :content="item.title" placement="top-start" :show-after="300">
                      <span class="novel-res-title">{{ item.title }}</span>
                    </el-tooltip>
                    <span class="vres-dur">{{ formatDur(item.duration) || item.duration_text || '' }}</span>
                    <el-tag size="small" type="info" effect="plain">{{ item.source }}</el-tag>
                    <el-button size="small" link type="primary" @click.stop="vPreview(item)">播放</el-button>
                    <el-button size="small" link @click.stop="openExternal(item.url)">官网</el-button>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane label="链接解析" name="link">
              <el-form-item label="链接">
                <el-input
                  v-model="linkUrl"
                  type="textarea"
                  :rows="3"
                  placeholder="粘贴视频链接，每行一条（支持多行批量解析）"
                />
              </el-form-item>
              <el-form-item label="解析方式">
                <el-select v-model="linkMode" style="width: 180px">
                  <el-option label="自动（推荐）" value="auto" />
                  <el-option label="yt-dlp" value="ytdlp" />
                  <el-option label="服务端嗅探" value="server" />
                  <el-option label="浏览器抓包（本部署未启用）" value="browser" disabled />
                </el-select>
              </el-form-item>
              <el-form-item label="标题">
                <el-input v-model="linkTitle" clearable placeholder="留空则用解析出的标题" />
              </el-form-item>
              <div class="actions">
                <el-button type="primary" :loading="linkResolving" @click="vResolveLink">解析</el-button>
              </div>
              <div v-if="linkInfo" class="link-info">
                <div>标题: {{ linkInfo.title }}</div>
                <div v-if="linkInfo.duration">时长: {{ formatDur(linkInfo.duration) }}</div>
                <div>
                  格式: {{ linkInfo.format }}
                  <span v-if="linkInfo.stage"> · 解析: {{ stageLabel(linkInfo.stage) }}</span>
                </div>
              </div>
              <div v-if="linkResults.length" class="link-results">
                <div v-for="(r, ri) in linkResults" :key="ri" class="link-result">
                  <div class="link-result-head">
                    <el-tag
                      size="small"
                      effect="light"
                      :type="r.error ? 'danger' : r.candidates.length ? 'success' : 'info'"
                    >
                      {{ r.error ? '失败' : stageLabel(r.stage) }}
                    </el-tag>
                    <span class="link-result-title">{{ r.title }}</span>
                    <span v-if="r.format" class="link-result-meta">{{ r.format }}</span>
                  </div>
                  <div v-if="r.error" class="link-result-error">{{ r.error }}</div>
                  <div v-else-if="r.type === 'album'" class="link-result-meta">
                    图集 {{ (r.image_urls || []).length }} 张，已填入图片自定义网址
                  </div>
                  <div v-else class="cand-list">
                    <div v-for="(c, ci) in r.candidates" :key="ci" class="cand-row">
                      <el-tag size="small" effect="plain" :type="c.ext === 'm3u8' ? 'warning' : 'success'">
                        {{ candKindLabel(c) }}
                      </el-tag>
                      <span v-if="c.quality" class="cand-quality">{{ c.quality }}</span>
                      <span class="cand-url" :title="c.url">{{ c.url }}</span>
                      <el-button size="small" type="primary" link @click="vPlayCandidate(r, c)">播放</el-button>
                      <el-button size="small" link @click="openExternal(c.url)">打开</el-button>
                    </div>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
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

      <el-card
        v-if="mode === 'novel'"
        shadow="never"
        class="player-card reader-card"
        :class="['reader-card-wrap', nReaderBgClass]"
      >
        <template #header>
          <div class="reader-header">
            <span class="player-title">
              <el-icon><Reading /></el-icon> 阅读器
              <span v-if="nReading" class="dim reader-book-title">{{ nReading.title }}</span>
            </span>
            <span v-if="nReading && nReading.author" class="reader-author">作者：{{ nReading.author }}</span>
            <el-button v-if="nReading" class="player-close" size="small" link @click="nCloseReader">关闭</el-button>
          </div>
        </template>
        <!-- 阅读工具栏 -->
        <div v-if="nReading" class="reader-toolbar">
          <div class="reader-toolbar-left">
            <el-select
              v-if="nHasChapters"
              v-model="nCurrentChapterIndex"
              size="small"
              class="reader-chapter-select"
              @change="nLoadChapter"
            >
              <el-option
                v-for="(ch, i) in nChapters"
                :key="ch.url"
                :label="`${i + 1}. ${ch.title}`"
                :value="i"
              />
            </el-select>
            <el-button
              v-if="nHasChapters"
              size="small"
              :disabled="nCurrentChapterIndex <= 0"
              @click="nPrevChapter"
            >
              <el-icon><ArrowLeft /></el-icon> 上一章
            </el-button>
            <el-button
              v-if="nHasChapters"
              size="small"
              :disabled="nCurrentChapterIndex >= nChapters.length - 1"
              @click="nNextChapter"
            >
              下一章 <el-icon><ArrowRight /></el-icon>
            </el-button>
            <span v-if="nCurrentChapterName" class="reader-chapter-name">{{ nCurrentChapterName }}</span>
          </div>
          <div class="reader-toolbar-right">
            <el-tooltip content="字号" placement="top">
              <div class="reader-font-group">
                <el-button size="small" circle @click="nSetFontSize(Math.max(12, nReaderSettings.fontSize - 2))">A-</el-button>
                <span class="reader-font-val">{{ nReaderSettings.fontSize }}</span>
                <el-button size="small" circle @click="nSetFontSize(Math.min(32, nReaderSettings.fontSize + 2))">A+</el-button>
              </div>
            </el-tooltip>
            <el-tooltip content="行距" placement="top">
              <div class="reader-font-group">
                <el-button size="small" circle @click="nSetLineHeight(Math.max(1.2, +(nReaderSettings.lineHeight - 0.2).toFixed(1)))">疏</el-button>
                <span class="reader-font-val">{{ nReaderSettings.lineHeight }}</span>
                <el-button size="small" circle @click="nSetLineHeight(Math.min(3.2, +(nReaderSettings.lineHeight + 0.2).toFixed(1)))">密</el-button>
              </div>
            </el-tooltip>
            <el-tooltip content="背景" placement="top">
              <div class="reader-bg-group">
                <button class="reader-bg-btn bg-day" :class="{ active: nReaderSettings.bgMode === 'day' }" @click="nSetBgMode('day')" title="白天"></button>
                <button class="reader-bg-btn bg-sepia" :class="{ active: nReaderSettings.bgMode === 'sepia' }" @click="nSetBgMode('sepia')" title="羊皮纸"></button>
                <button class="reader-bg-btn bg-night" :class="{ active: nReaderSettings.bgMode === 'night' }" @click="nSetBgMode('night')" title="夜间"></button>
              </div>
            </el-tooltip>
          </div>
        </div>
        <div v-if="nContentLoading" class="preview-loading">加载正文中...</div>
        <template v-else-if="nContent">
          <div v-if="nSummary" class="novel-summary">{{ nSummary }}</div>
          <div class="novel-reader-body">
            <div
              class="novel-content"
              :style="{ fontSize: nReaderSettings.fontSize + 'px', lineHeight: nReaderSettings.lineHeight }"
            >{{ nContent }}</div>
          </div>
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

      <el-card v-if="mode === 'video'" shadow="never" class="progress-card">
        <template #header>播放日志</template>
        <el-empty v-if="!videoLogs.length" description="搜索并点击结果后，这里会显示解析与播放过程" :image-size="60" />
        <div v-else class="logs vlogs">
          <div v-for="(l, i) in videoLogs" :key="i" class="log-line">{{ l }}</div>
        </div>
      </el-card>

      <el-card v-show="mode === 'video'" shadow="never" class="player-card preview-card">
        <template #header>
          放映室
          <span v-if="playerTitle" class="dim">{{ playerTitle }}</span>
        </template>
        <div v-if="playerLoading" class="preview-loading">解析视频中，请稍候...</div>
        <div v-show="playerReady" class="player-box" @click="onPlayerClick">
          <div class="player-wrap" :style="{ height: playerHeight + 'px' }">
            <video
              ref="videoRef"
              :src="playerSrc || undefined"
              controls
              autoplay
              playsinline
              class="player-video"
              @click="onPlayerClick"
              @pointerdown="onPlayerClick"
              @play="onVideoPlay"
              @playing="onVideoPlaying"
              @pause="onVideoPause"
              @seeked="onVideoSeek"
              @timeupdate="onVideoTime"
            ></video>
            <audio
              v-if="playerAudioSrc"
              ref="audioRef"
              :src="playerAudioSrc"
              preload="auto"
              class="player-audio"
              @error="onAudioError"
            ></audio>
          </div>
          <div class="player-tools">
            <span v-if="playerHint" class="hint">{{ playerHint }}</span>
            <el-button
              v-if="playerItemUrl"
              size="small"
              type="primary"
              plain
              @click.stop="openExternal(playerItemUrl)"
            >
              在官网打开（本页预览可能受限）
            </el-button>
          </div>
          <div class="player-handle" title="拖动调整高度" @mousedown="startPlayerDrag">
            <span class="handle-grip"></span>
          </div>
        </div>
        <el-empty
          v-show="!playerLoading && !playerReady"
          description="点击左侧搜索结果任意一行即可播放"
          :image-size="60"
        />
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
.novel-kw-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.novel-kw-row .el-input {
  flex: 1;
}
.novel-cat-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.novel-cat-label {
  font-size: 12px;
  color: var(--text-sub);
  white-space: nowrap;
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
.res-title-orig {
  display: inline-block;
  margin-left: 6px;
  font-size: 11px;
  color: var(--text-sub);
  opacity: 0.65;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
  vertical-align: baseline;
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
.reader-card :deep(.el-card__body) {
  padding: 22px;
}
.reader-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.reader-book-title {
  font-weight: 600;
}
.reader-author {
  font-size: 12px;
  color: #8b7355;
}
.reader-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  margin-bottom: 10px;
  border-bottom: 1px solid #e5e0d8;
  flex-wrap: wrap;
}
.reader-toolbar-left,
.reader-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.reader-chapter-select {
  width: 200px;
}
.reader-chapter-name {
  font-size: 13px;
  color: #6b7280;
  margin-left: 8px;
}
.reader-font-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.reader-font-val {
  font-size: 12px;
  color: #888;
  min-width: 24px;
  text-align: center;
}
.reader-bg-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.reader-bg-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid #ccc;
  cursor: pointer;
  transition: border-color 0.2s;
}
.reader-bg-btn.active {
  border-color: #d97706;
  box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.3);
}
.bg-day {
  background: #ffffff;
}
.bg-sepia {
  background: #f5f0e8;
}
.bg-night {
  background: #1a1a2e;
}
.novel-reader-body {
  max-height: 65vh;
  overflow-y: auto;
  border-radius: 4px;
}
.novel-content {
  border: 0;
  border-radius: 4px;
  padding: 28px clamp(20px, 5vw, 72px);
  box-shadow: inset 0 0 50px rgba(120, 83, 31, 0.07);
  font: Georgia, 'Noto Serif SC', serif;
  white-space: pre-wrap;
}
/* Day mode */
.reader-bg-day .novel-content {
  color: #303133;
  background: #ffffff;
}
.reader-bg-day .novel-reader-body {
  background: #f8f9fa;
}
/* Sepia mode */
.reader-bg-sepia .novel-content {
  color: #3f3528;
  background: #fffdf6;
}
.reader-bg-sepia .novel-reader-body {
  background: #f8f4ec;
}
/* Night mode */
.reader-bg-night .novel-content {
  color: #d4cfc4;
  background: #1a1a2e;
}
.reader-bg-night .novel-reader-body {
  background: #16162a;
}
.reader-bg-night .reader-toolbar {
  border-bottom-color: #2a2a4a;
}
.reader-bg-night .reader-chapter-name {
  color: #888;
}
[data-theme='dark'] .novel-content {
  color: #ded5c6;
  background: #211f1b;
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
.player-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.player-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.player-close {
  flex-shrink: 0;
}
.vres-item {
  cursor: pointer;
  transition: background 0.15s;
}
.vres-item:hover {
  background: #f5f7fa;
}

.mobile-nav {
  display: none;
}

@media (max-width: 991px) {
  .workspace {
    flex-direction: column;
    gap: 12px;
  }
  .left {
    width: 100% !important;
    flex-shrink: 1;
  }
  .left-handle {
    display: none;
  }
  .right {
    width: 100%;
  }
  .player-card {
    position: static;
    z-index: auto;
    margin: 12px 0 0;
    border-radius: 8px;
    background: var(--card);
    overflow: visible;
  }
  .player-card .el-card__body {
    padding-bottom: 20px;
  }
  .player-card .el-card__header {
    position: static;
  }
  .mobile-nav {
    display: flex;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 900;
    background: var(--card);
    border-top: 1px solid var(--border);
    padding-bottom: env(safe-area-inset-bottom);
  }
  .mobile-nav-item {
    flex: 1;
    height: 50px;
    border: none;
    background: transparent;
    color: var(--text-sub);
    font-size: 15px;
    cursor: pointer;
    border-top: 2px solid transparent;
    transition: color 0.2s ease, border-color 0.2s ease;
  }
  .mobile-nav-item.active {
    color: var(--brand);
    border-top-color: var(--brand);
    font-weight: 600;
  }
  .card-head {
    flex-wrap: wrap;
    gap: 8px;
  }
  .head-right {
    flex-wrap: wrap;
  }
  .el-form-item {
    margin-bottom: 14px;
  }
  .actions .el-button,
  .actions .el-button + .el-button {
    margin-left: 0;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .actions .el-button {
    flex: 1;
    min-height: 40px;
    margin-left: 0;
  }
  .gallery {
    grid-template-columns: repeat(3, 1fr) !important;
  }
  .comic-wall {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}

/* Match the textbook workspace rhythm: hero, search deck, then result cards. */
.workspace {
  display: block;
  max-width: 1400px;
  margin: 0 auto;
}
.crawl-hero {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  min-height: 170px;
  overflow: hidden;
  padding: 30px 34px;
  border-radius: 18px 18px 0 0;
  color: #eff6ff;
  background: radial-gradient(circle at 80% 10%, rgba(56, 189, 248, .3), transparent 28%), linear-gradient(125deg, #172554 0%, #1e3a8a 54%, #0f766e 120%);
}
.crawl-hero::after {
  content: '';
  position: absolute;
  right: 18%;
  bottom: -65px;
  width: 180px;
  height: 180px;
  border: 1px solid rgba(255,255,255,.15);
  transform: rotate(24deg);
}
.crawl-hero > div { position: relative; z-index: 1; }
.crawl-hero .eyebrow { color: #7dd3fc; font: 600 11px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .2em; }
.crawl-hero h1 { margin: 8px 0 5px; font: 700 34px/1.15 Georgia, 'Noto Serif SC', serif; letter-spacing: .04em; }
.crawl-hero p { max-width: 700px; margin: 0; color: #bfdbfe; font-size: 14px; }
.hero-mark { display: grid; width: 112px; height: 112px; place-items: center; border: 1px solid rgba(255,255,255,.2); border-radius: 18px; color: #bae6fd; background: rgba(15,23,42,.18); font: 700 18px ui-monospace, monospace; letter-spacing: .12em; transform: rotate(8deg); }
.left { width: 100% !important; }
.left-handle { display: none; }
.left > .el-card { border-top: 0; border-radius: 0 0 18px 18px; box-shadow: 0 14px 30px rgba(15,23,42,.08) !important; }
.right { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 24px; }
.right > .el-card { min-width: 0; border-radius: 14px; }
.card-head { font-weight: 600; }
.player-card { min-width: 0; }

@media (max-width: 900px) {
  .right { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .crawl-hero { min-height: 145px; padding: 24px 20px; }
  .crawl-hero h1 { font-size: 28px; }
  .hero-mark { display: none; }
  .right { margin-top: 16px; }
}

/* ---- 视频 ---- */
.video-form { width: 100%; }
.vresults { margin-top: 12px; }
.vres-item { cursor: pointer; }
.vres-item:hover { background: rgba(37, 99, 235, 0.06); }
.vres-item.active { background: rgba(37, 99, 235, 0.12); }
.vres-item .novel-res-title { flex: 1; min-width: 0; }
.link-results {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow-y: auto;
  margin-top: 10px;
}
.link-result {
  border: 1px solid var(--border, #ebeef5);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--card-soft, #f5f7fa);
}
.link-result-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.link-result-title { flex: 1; min-width: 0; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.link-result-meta { color: var(--text-sub, #909399); font-size: 12px; }
.link-result-error { color: #f56c6c; font-size: 12px; margin-top: 6px; word-break: break-all; }
.cand-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.cand-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 12px;
}
.cand-quality { flex-shrink: 0; color: var(--text-sub, #909399); }
.cand-url {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-sub, #909399);
}
.vlogs { max-height: 300px; overflow-y: auto; }
.player-box { position: relative; }
.player-tools { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
/* 音频元素不参与显示，但仍需留在 DOM 中发声 */
.player-audio {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.progress-card, .preview-card { min-width: 0; }

</style>
