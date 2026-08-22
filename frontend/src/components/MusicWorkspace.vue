<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const props = defineProps({ active: { type: Boolean, default: false } })

const keyword = ref('')
const selectedSource = ref('all')
const sources = ref({})
const items = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const page = ref(1)
const audio = ref(null)
const playingId = ref('')

const downloadable = computed(() => items.value.filter((item) => item.download_candidates?.length))

function itemKey(item) { return `${item.source}:${item.id}` }
function artistText(item) { return (item.artists || []).join(', ') || '未知音乐人' }
function formatDuration(seconds) {
  if (!Number.isFinite(Number(seconds))) return '--:--'
  const v = Math.max(0, Math.round(Number(seconds)))
  return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`
}
function formatBytes(value) {
  const b = Number(value || 0)
  if (!b) return '未知'
  if (b >= 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${Math.ceil(b / 1024)} KB`
}
function candidateFilename(item, c) {
  const ext = c.format || 'mp3'
  const safe = (item.title || 'music').replace(/[^\w\u4e00-\u9fff -]/g, '_').slice(0, 80)
  return `${safe}.${ext}`
}
async function loadSources() {
  try { sources.value = await api.musicSources() } catch (e) { ElMessage.warning(e.message) }
}
async function search(append = false) {
  if (!keyword.value.trim()) { ElMessage.warning('请输入歌曲、音乐人或专辑名称'); return }
  append ? (loadingMore.value = true) : (loading.value = true)
  try {
    const np = append ? page.value + 1 : 1
    const result = await api.musicSearch({ keyword: keyword.value.trim(), source: selectedSource.value, page: np, page_size: 12 })
    const incoming = result.items || []
    if (append) {
      const map = new Map([...items.value, ...incoming].map((i) => [itemKey(i), i]))
      items.value = [...map.values()]
    } else {
      stopPreview(); items.value = incoming
    }
    page.value = np
    if (!append && !incoming.length) ElMessage.info('没有找到结果')
  } catch (e) { ElMessage.error(e.message) } finally { loading.value = false; loadingMore.value = false }
}
async function play(item) {
  if (!item.preview_url) { ElMessage.info('没有可试听音频'); return }
  if (playingId.value === itemKey(item) && audio.value && !audio.value.paused) { audio.value.pause(); playingId.value = ''; return }
  playingId.value = itemKey(item)
  audio.value.src = api.musicPreviewUrl(item.preview_url)
  audio.value.load()
  try { await audio.value.play() } catch (e) { playingId.value = ''; ElMessage.error('试听失败: ' + e.message) }
}
function stopPreview() {
  if (audio.value) { audio.value.pause(); audio.value.removeAttribute('src'); audio.value.load() }
  playingId.value = ''
}
function downloadItem(item, candidate) {
  if (!candidate) return
  const a = document.createElement('a')
  a.href = api.musicDownloadUrl(candidate.url, candidateFilename(item, candidate))
  a.download = candidateFilename(item, candidate)
  a.target = '_blank'
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  ElMessage.success('正在下载...')
}
function openLink(url) {
  if (/^https?:\/\//i.test(url || '')) window.open(url, '_blank', 'noopener,noreferrer')
}
watch(() => props.active, (a) => { if (!a && audio.value && !audio.value.paused) audio.value.pause() })
onMounted(loadSources)
</script>

<template>
  <section class="music-space">
    <header class="music-hero">
      <div>
        <span class="eyebrow">OPEN AUDIO ARCHIVE</span>
        <h1>开放音乐采集室</h1>
        <p>检索、试听并保存明确开放或来源允许下载的音乐，不绕过付费与数字版权保护。</p>
      </div>
      <div class="hero-disc"><span></span></div>
    </header>
    <div class="console">
      <div class="search-line">
        <el-input v-model="keyword" size="large" clearable placeholder="歌曲、音乐人或专辑" @keyup.enter="search(false)">
          <template #prefix><el-icon><Headset /></el-icon></template>
        </el-input>
        <el-button type="primary" size="large" :loading="loading" @click="search(false)">搜索</el-button>
      </div>
      <div class="control-line">
        <el-select v-model="selectedSource" aria-label="音乐源">
          <el-option label="全部开放源" value="all" />
          <el-option v-for="(name, id) in sources" :key="id" :value="id">{{ name }}</el-option>
        </el-select>
        <span class="source-note">Internet Archive | Wikimedia | Audius | Jamendo</span>
      </div>
    </div>
    <div class="now-playing">
      <div class="pulse" :class="{ active: playingId }"><i></i><i></i><i></i><i></i></div>
      <div>
        <b>{{ playingId ? items.find((i) => itemKey(i) === playingId)?.title : '试听台' }}</b>
        <span>{{ playingId ? artistText(items.find((i) => itemKey(i) === playingId) || {}) : '选择一首音乐开始试听' }}</span>
      </div>
      <audio ref="audio" controls @ended="playingId = ''" />
    </div>
    <div v-if="items.length" class="batch-bar">
      <div><strong>{{ items.length }}</strong> 条结果 · <strong>{{ downloadable.length }}</strong> 条允许下载</div>
    </div>
    <div v-loading="loading" class="track-list">
      <article v-for="(item, index) in items" :key="itemKey(item)" class="track">
        <span class="idx">{{ String(index + 1).padStart(2, '0') }}</span>
        <div class="cover">
          <img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" loading="lazy" referrerpolicy="no-referrer" />
          <el-icon v-else><Headset /></el-icon>
          <button v-if="item.preview_url" type="button" class="play" @click="play(item)">
            <el-icon><VideoPause v-if="playingId === itemKey(item)" /><VideoPlay v-else /></el-icon>
          </button>
        </div>
        <div class="track-main">
          <div class="source-row"><span>{{ item.source.replace(/_/g, ' ') }}</span><em v-if="item.license">{{ item.license }}</em></div>
          <h2>{{ item.title }}</h2>
          <p>{{ artistText(item) }}<span v-if="item.album"> · {{ item.album }}</span></p>
        </div>
        <div class="track-meta"><b>{{ formatDuration(item.duration) }}</b><span>{{ item.year || '未知' }}</span></div>
        <div class="track-actions">
          <el-button v-if="item.detail_url" text @click="openLink(item.detail_url)">来源</el-button>
          <template v-if="item.download_candidates?.length">
            <el-dropdown trigger="click">
              <el-button type="success" plain>下载 <el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="c in item.download_candidates" :key="c.url" @click="downloadItem(item, c)">
                    {{ c.format.toUpperCase() }} · {{ formatBytes(c.size) }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <el-tag v-else size="small" type="info">仅试听</el-tag>
        </div>
      </article>
      <el-empty v-if="!loading && !items.length" description="搜索开放许可音乐，结果会在这里排成播放队列">
        <template #image><el-icon class="empty-icon"><Headset /></el-icon></template>
      </el-empty>
      <div v-if="items.length" class="load-more"><el-button :loading="loadingMore" @click="search(true)">加载下一页</el-button></div>
    </div>
  </section>
</template>

<style scoped>
.music-space { max-width: 1200px; margin: 0 auto; color: var(--text); }
.music-hero { position: relative; display: flex; align-items: center; justify-content: space-between; min-height: 160px; overflow: hidden; padding: 26px 32px; border-radius: 18px 18px 0 0; color: #f8fafc; background: radial-gradient(circle at 72% 20%, rgba(45,212,191,.24), transparent 30%), linear-gradient(125deg, #111827, #172554 55%, #134e4a); }
.music-hero::before { content: ''; position: absolute; inset: 0; opacity: .18; background: repeating-linear-gradient(90deg, transparent 0 34px, rgba(255,255,255,.08) 35px 36px); }
.music-hero > div { position: relative; z-index: 1; }
.eyebrow { color: #5eead4; font: 700 11px ui-monospace, monospace; letter-spacing: .22em; }
.music-hero h1 { margin: 8px 0 6px; font: 800 32px/1.1 'Arial Narrow', 'Microsoft YaHei', sans-serif; letter-spacing: .04em; }
.music-hero p { max-width: 600px; margin: 0; color: #cbd5e1; font-size: 13px; }
.hero-disc { display: grid; width: 100px; height: 100px; place-items: center; border-radius: 50%; background: repeating-radial-gradient(circle, #111827 0 4px, #334155 5px 7px); box-shadow: 0 16px 35px rgba(0,0,0,.4); animation: spin 12s linear infinite; }
.hero-disc span { width: 32px; height: 32px; border: 7px solid #fb7185; border-radius: 50%; background: #f8fafc; }
@keyframes spin { to { transform: rotate(360deg); } }
.console { padding: 18px 22px; border: 1px solid var(--border); border-top: 0; border-radius: 0 0 16px 16px; background: var(--card); box-shadow: 0 12px 28px rgba(15,23,42,.08); }
.search-line { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; }
.control-line { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
.control-line .el-select { width: 220px; }
.source-note { margin-left: auto; color: var(--text-sub); font: 11px ui-monospace, monospace; }
.now-playing { display: grid; grid-template-columns: 48px minmax(140px, 1fr) minmax(280px, 500px); align-items: center; gap: 12px; margin: 16px 0; padding: 11px 16px; border: 1px solid #1e293b; border-radius: 12px; color: #e2e8f0; background: #0f172a; }
.now-playing > div:nth-child(2) { display: grid; min-width: 0; }
.now-playing b, .now-playing span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.now-playing span { color: #94a3b8; font-size: 12px; }
.now-playing audio { width: 100%; height: 34px; }
.pulse { display: flex; align-items: end; justify-content: center; gap: 3px; height: 24px; }
.pulse i { width: 4px; height: 7px; border-radius: 4px; background: #2dd4bf; }
.pulse.active i { animation: level .8s ease-in-out infinite alternate; }
.pulse.active i:nth-child(2) { animation-delay: -.4s; height: 18px; }
.pulse.active i:nth-child(3) { animation-delay: -.2s; height: 13px; }
@keyframes level { to { height: 23px; } }
.batch-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; color: var(--text-sub); font-size: 13px; }
.track-list { min-height: 300px; }
.track { display: grid; grid-template-columns: 38px 68px minmax(0, 1fr) 82px 160px; align-items: center; gap: 12px; margin-bottom: 8px; padding: 10px 14px; border: 1px solid var(--border); border-radius: 13px; background: var(--card); transition: border-color .2s, transform .2s, box-shadow .2s; }
.track:hover { transform: translateY(-1px); border-color: #5eead4; box-shadow: 0 9px 22px rgba(15,23,42,.08); }
.idx { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; color: var(--text-sub); background: var(--card-soft); font: 700 11px ui-monospace, monospace; }
.cover { position: relative; display: grid; width: 62px; height: 62px; place-items: center; overflow: hidden; border-radius: 10px; color: #5eead4; background: linear-gradient(135deg, #1e293b, #134e4a); font-size: 24px; }
.cover img { width: 100%; height: 100%; object-fit: cover; }
.play { position: absolute; display: grid; width: 32px; height: 32px; place-items: center; border: 0; border-radius: 50%; color: #fff; background: rgba(15,23,42,.78); cursor: pointer; opacity: 0; transition: opacity .2s; }
.cover:hover .play, .track:hover .play { opacity: 1; }
.track-main { min-width: 0; }
.source-row { display: flex; align-items: center; gap: 8px; color: #0f766e; font: 700 10px ui-monospace, monospace; text-transform: uppercase; }
.source-row em { overflow: hidden; color: #64748b; font-style: normal; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.track h2 { overflow: hidden; margin: 4px 0; font-size: 16px; line-height: 1.25; text-overflow: ellipsis; white-space: nowrap; }
.track-main p { overflow: hidden; margin: 0; color: var(--text-sub); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.track-meta { display: grid; color: var(--text-sub); font-size: 11px; text-align: right; }
.track-meta b { color: var(--text); font: 700 13px ui-monospace, monospace; }
.track-actions { display: flex; align-items: center; justify-content: flex-end; gap: 4px; }
.load-more { padding: 18px; text-align: center; }
.empty-icon { color: #2dd4bf; font-size: 70px; }
@media (max-width: 900px) { .source-note { display: none; } .track { grid-template-columns: 36px 62px minmax(0,1fr) auto; } .track-meta { display: none; } .track-actions { grid-column: 3 / -1; justify-content: flex-start; } }
@media (max-width: 650px) { .music-hero { min-height: 145px; padding: 24px 20px; } .music-hero h1 { font-size: 28px; } .hero-disc { display: none; } .console { padding: 15px; } .search-line { grid-template-columns: 1fr; } .control-line { align-items: stretch; flex-direction: column; } .control-line .el-select { width: 100%; } .now-playing { grid-template-columns: 40px minmax(0,1fr); } .now-playing audio { grid-column: 1 / -1; } .batch-bar { align-items: flex-start; flex-direction: column; gap: 8px; } .track { grid-template-columns: 32px 56px minmax(0,1fr); padding: 9px; gap: 8px; } .cover { width: 54px; height: 54px; } .track-actions { grid-column: 2 / -1; } .source-row em { display: none; } }
</style>