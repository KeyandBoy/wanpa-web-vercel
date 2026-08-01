const qs = (p) => new URLSearchParams(p).toString()

export const isLocal = () =>
  ['localhost', '127.0.0.1', '::1', '[::1]'].includes(location.hostname)

export const api = {
  search: (params) =>
    fetch(`/api/search?${qs(params)}`).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '搜索失败')
      return r.json()
    }),
  pageImages: (url) =>
    fetch(`/api/page-images?url=${encodeURIComponent(url)}`).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '网页解析失败')
      return r.json()
    }),
  proxyUrl: (url) => `/api/proxy?url=${encodeURIComponent(url)}`,
  uploadBlob: (taskId, seq, ext, blob) =>
    fetch(`/api/blob-upload?task_id=${taskId}&seq=${seq}&ext=${ext}`, {
      method: 'POST',
      body: blob,
    }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '上传失败')
      return r.json()
    }),
  cleanupBlob: (prefix) =>
    fetch('/api/blob-cleanup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prefix }),
    }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '清理失败')
      return r.json()
    }),
  novelSearch: (params) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60000)
    return fetch(`/api/novel-search?${qs(params)}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '小说搜索失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  novelContent: (url, translate) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60000)
    return fetch(`/api/novel-content?url=${encodeURIComponent(url)}&translate=${translate ? 1 : 0}`, {
      signal: ctrl.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '内容获取失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  novelChapters: (url) =>
    fetch(`/api/novel-chapters?url=${encodeURIComponent(url)}`).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '目录获取失败')
      return r.json()
    }),
  dsSummarize: (text) =>
    fetch('/api/ds-summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '摘要生成失败')
      return r.json()
    }),
  dsFilter: (keyword, items) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 40000)
    return fetch('/api/ds-filter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword, items }),
      signal: ctrl.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '筛选失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  dsClean: (text) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 40000)
    return fetch('/api/ds-clean', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: ctrl.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '清理失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
}
