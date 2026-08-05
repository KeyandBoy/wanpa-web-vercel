import { api } from './api'

const WATERMARK_MARKS = ['watermark', 'shuiyin', 'logo', 'mark', 'sign']

export const canPickFolder = () =>
  typeof window !== 'undefined' && typeof window.showDirectoryPicker === 'function'

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function md5Hex(blob) {
  const buf = await blob.arrayBuffer()
  const d = await crypto.subtle.digest('SHA-256', buf)
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function extFromType(type) {
  const t = (type || '').split('/')[1] || ''
  if (['png', 'gif', 'webp'].includes(t)) return t
  return 'jpg'
}

function passFilter(item, { minWidth, minHeight, noWatermark }) {
  if (minWidth > 0 && item.width && item.width < minWidth) return false
  if (minHeight > 0 && item.height && item.height < minHeight) return false
  if (!noWatermark) {
    const text = `${item.url} ${item.title || ''}`.toLowerCase()
    if (WATERMARK_MARKS.some((m) => text.includes(m))) return false
  }
  return true
}

export function passLayers(item, rules) {
  if (!rules || !rules.length) return true
  for (const rule of rules) {
    const words = (rule.words || '')
      .split(/[,，、\s]+/)
      .map((w) => w.trim().toLowerCase())
      .filter(Boolean)
    if (!words.length) continue
    const hay = (
      rule.field === 'title'
        ? item.title || ''
        : rule.field === 'url'
          ? item.url || ''
          : `${item.title || ''} ${item.url || ''}`
    ).toLowerCase()
    const hit = words.some((w) => hay.includes(w))
    if (rule.mode === 'exclude' && hit) return false
    if (rule.mode === 'include' && !hit) return false
  }
  return true
}

async function fetchImage(url, signal) {
  const res = await fetch(api.proxyUrl(url), { signal })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.blob()
}

async function collectItems(keyword, source, target, filters, signal, onLog) {
  const items = []
  const seenUrls = new Set()
  let page = 1
  let hasMore = true
  while (items.length < target * 3 && hasMore && page <= 10 && !signal?.aborted) {
    const r = await api.search({ keyword, source, page })
    const list = (r.items || []).filter((i) => {
      if (!passFilter(i, filters)) return false
      if (seenUrls.has(i.url)) return false
      seenUrls.add(i.url)
      return true
    })
    items.push(...list)
    hasMore = r.has_more !== false
    page += 1
    await sleep(300)
  }
  onLog?.(`${source}: 解析到 ${items.length} 张候选(已翻 ${page - 1} 页)`)
  return items
}

async function pool(items, workers, fn) {
  let i = 0
  const run = async () => {
    while (i < items.length) {
      const idx = i++
      await fn(items[idx], idx)
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(Math.max(workers, 1), items.length || 1) }, run)
  )
}

function balanceGroups(items, target) {
  if (!items.length || !items.some((i) => i.group)) return items
  const groups = new Map()
  for (const it of items) {
    const g = it.group || '_other'
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g).push(it)
  }
  if (groups.size <= 1) return items
  const per = Math.ceil(target / groups.size)
  const out = []
  for (const arr of groups.values()) {
    out.push(...arr.slice(0, per))
  }
  return out
}

export async function runCrawl({
  keyword,
  sources,
  count,
  minWidth = 0,
  minHeight = 0,
  noWatermark = false,
  workers = 4,
  customUrls = '',
  layers = [],
  sink,
  onProgress,
  onLog,
  signal,
}) {
  const meta = []
  let downloaded = 0
  let dup = 0
  let failed = 0
  let skipped = 0
  const seenHashes = new Set()
  const emit = () =>
    onProgress?.({ downloaded, dup, failed, skipped, total: count * sources.length, images: meta.length })

  for (const source of sources) {
    if (signal?.aborted) break
    onLog?.(`数据源: ${source}`)
    let items = []
    try {
      if (source === 'custom') {
        const urls = customUrls
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean)
        if (!urls.length) {
          throw new Error('未填写自定义网址')
        }
        for (const u of urls) {
          if (signal?.aborted) break
          const r = await api.pageImages(u)
          items.push(...(r.items || []).map((i) => ({ ...i, sourceUrl: u })))
          onLog?.(`自定义网址: ${u} → 提取 ${(r.items || []).length} 张`)
        }
        const seenUrls = new Set()
        items = items.filter((i) => {
          if (seenUrls.has(i.url)) return false
          seenUrls.add(i.url)
          return true
        })
        if (!items.length) {
          throw new Error('这些网址中没有提取到图片')
        }
        onLog?.(`自定义网址: 共 ${items.length} 张候选(去重后)`)
      } else {
        items = await collectItems(
          keyword,
          source,
          count,
          { minWidth, minHeight, noWatermark },
          signal,
          onLog
        )
      }
      if (layers.length) {
        const before = items.length
        items = items.filter((it) => passLayers(it, layers))
        if (items.length !== before) {
          onLog?.(`${source}: 多层筛选 ${before} → ${items.length} 条`)
        }
        if (!items.length) {
          onLog?.(`${source}: 筛选后无匹配结果，跳过该源`)
          skipped += 1
          emit()
          continue
        }
      }
      const beforeBalance = items.length
      items = balanceGroups(items, count)
      if (items.length !== beforeBalance) {
        onLog?.(`${source}: 按图集均分 ${beforeBalance} → ${items.length} 张`)
      }
    } catch (e) {
      if (e.name === 'AbortError') continue
      onLog?.(`${source}: 搜索失败 ${e.message}`)
      failed += 1
      emit()
      continue
    }
    let srcDownloaded = 0
    let srcFailed = 0
    let seq = 0
    await pool(items, workers, async (item) => {
      if (signal?.aborted) return
      if (srcDownloaded >= count) return
      try {
        const blob = await fetchImage(item.url, signal)
        const digest = await md5Hex(blob)
        if (seenHashes.has(digest)) {
          dup += 1
          emit()
          return
        }
        seenHashes.add(digest)
        seq += 1
        const ext = extFromType(blob.type)
        const path = `${keyword}/图片/${source}/${keyword}_${source}_${String(seq).padStart(3, '0')}.${ext}`
        const saved = await sink.save({ path, seq, blob, item })
        meta.push({
          keyword,
          source,
          url: item.url,
          path,
          width: item.width ?? null,
          height: item.height ?? null,
          size_bytes: blob.size,
          hash: digest,
          remote_url: saved?.remoteUrl ?? null,
        })
        downloaded += 1
        srcDownloaded += 1
        onProgress?.({ type: 'image', path, previewUrl: saved?.previewUrl })
        emit()
      } catch (e) {
        if (e.name === 'AbortError') return
        failed += 1
        srcFailed += 1
        if (failed <= 8) {
          onLog?.(`${source}: 下载失败: ${e.message} | ${item.url.slice(0, 100)}`)
        }
        emit()
      }
    })
    if (signal?.aborted) break
    const srcMeta = meta.filter((m) => m.source === source)
    if (srcMeta.length) {
      await sink.writeMetadata(
        `${keyword}/图片/${source}/metadata.json`,
        srcMeta.map(({ remote_url, ...rest }) => rest)
      )
    }
    onLog?.(`${source}: 下载 ${srcDownloaded} | 去重跳过 ${dup} | 失败 ${srcFailed}`)
  }

  const all = meta.map(({ remote_url, ...rest }) => rest)
  if (all.length) {
    await sink.writeMetadata(`${keyword}/图片/metadata.json`, all)
  }
  onLog?.(`任务结束: 共下载 ${downloaded} 张 | 去重 ${dup} | 失败 ${failed}`)
  return { meta }
}

export function createFolderSink() {
  return {
    dirHandle: null,
    async init() {
      this.dirHandle = await window.showDirectoryPicker({ id: 'getphoto' })
      return this.dirHandle
    },
    async prepare(subdirs) {
      const perm = await this.dirHandle.requestPermission({ mode: 'readwrite' })
      if (perm !== 'granted') throw new Error('文件夹写入权限被拒绝')
      for (const d of subdirs) {
        let dir = this.dirHandle
        for (const p of d.split('/')) {
          dir = await dir.getDirectoryHandle(p, { create: true })
        }
      }
    },
    async save({ path, blob }) {
      const parts = path.split('/')
      let dir = this.dirHandle
      for (const p of parts.slice(0, -1)) {
        dir = await dir.getDirectoryHandle(p, { create: true })
      }
      const fh = await dir.getFileHandle(parts[parts.length - 1], { create: true })
      const w = await fh.createWritable()
      await w.write(blob)
      await w.close()
      const file = await fh.getFile()
      return { previewUrl: URL.createObjectURL(file) }
    },
    async saveStream(path, res) {
      const parts = path.split('/')
      let dir = this.dirHandle
      for (const p of parts.slice(0, -1)) {
        dir = await dir.getDirectoryHandle(p, { create: true })
      }
      const fh = await dir.getFileHandle(parts[parts.length - 1], { create: true })
      const w = await fh.createWritable()
      const reader = res.body.getReader()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        await w.write(value)
      }
      await w.close()
    },
    async saveStreamProgress(path, res, onProgress) {
      const parts = path.split('/')
      let dir = this.dirHandle
      for (const p of parts.slice(0, -1)) {
        dir = await dir.getDirectoryHandle(p, { create: true })
      }
      const fh = await dir.getFileHandle(parts[parts.length - 1], { create: true })
      const w = await fh.createWritable()
      const reader = res.body.getReader()
      let dl = 0
      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          await w.write(value)
          dl += value.length
          onProgress?.(dl)
        }
        await w.close()
      } catch (e) {
        try {
          await w.abort()
        } catch {
          /* ignore */
        }
        throw e
      }
    },
    async writeMetadata(path, meta) {
      if (!meta.length) return
      const parts = path.split('/')
      let dir = this.dirHandle
      for (const p of parts.slice(0, -1)) {
        dir = await dir.getDirectoryHandle(p, { create: true })
      }
      const fh = await dir.getFileHandle(parts[parts.length - 1], { create: true })
      const w = await fh.createWritable()
      await w.write(JSON.stringify(meta, null, 2))
      await w.close()
    },
  }
}

export function createMemorySink() {
  const files = []
  return {
    async save({ path, blob }) {
      files.push({ path, blob })
      return { previewUrl: URL.createObjectURL(blob) }
    },
    async writeMetadata(path, meta) {
      if (meta.length) {
        files.push({
          path,
          blob: new Blob([JSON.stringify(meta, null, 2)], { type: 'application/json' }),
        })
      }
    },
    getFiles: () => files,
  }
}

export function createBlobSink(taskId) {
  const urls = []
  return {
    async save({ path, seq, blob }) {
      const ext = extFromType(blob.type)
      const r = await api.uploadBlob(taskId, seq, ext, blob)
      urls.push(r.url)
      return { previewUrl: r.url, remoteUrl: r.url }
    },
    async writeMetadata(path, meta) {
      if (meta.length) {
        const blob = new Blob([JSON.stringify(meta, null, 2)], { type: 'application/json' })
        const r = await api.uploadBlob(taskId, `meta_${meta.length}_${Date.now()}`, blob)
        urls.push(r.url)
      }
    },
    getUrls: () => urls,
    async cleanup() {
      await api.cleanupBlob(taskId)
    },
  }
}

export async function downloadZip(files, zipName, onProgress) {
  const { default: JSZip } = await import('jszip')
  const zip = new JSZip()
  for (const f of files) zip.file(f.path, f.blob)
  const blob = await zip.generateAsync({ type: 'blob' }, (m) => onProgress?.(m.percent))
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = zipName
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 10000)
}

export function sanitizeName(name) {
  return name
    .replace(/[\\/:*?"<>|\r\n\t]+/g, '_')
    .replace(/\.+$/, '')
    .trim()
    .slice(0, 120) || 'video'
}

export function formatDur(sec) {
  if (!sec && sec !== 0) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  if (m >= 60) return `${Math.floor(m / 60)}小时${m % 60}分`
  return m ? `${m}分${s}秒` : `${s}秒`
}
