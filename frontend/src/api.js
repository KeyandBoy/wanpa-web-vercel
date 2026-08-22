import { currentToken } from './license'

const qs = (p) => new URLSearchParams(p).toString()

export const isLocal = () =>
  ['localhost', '127.0.0.1', '::1', '[::1]'].includes(location.hostname)

// 附加激活 token（Plus 源请求需要）
const tok = () => {
  const t = currentToken()
  return t ? { token: t } : {}
}

export const api = {
  search: (params) =>
    fetch(`/api/search?${qs({ ...params, ...tok() })}`).then(async (r) => {
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
  comicSearch: (params) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 90000)
    return fetch(`/api/comic-search?${qs({ ...params, ...tok() })}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '漫画搜索失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  comicPages: (url, limit) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 90000)
    const p = { url, ...tok() }
    if (limit) p.limit = limit
    return fetch(`/api/comic-pages?${qs(p)}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '漫画内容获取失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  novelSearch: (params) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60000)
    return fetch(`/api/novel-search?${qs({ ...params, ...tok() })}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '小说搜索失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  novelContent: (url, translate) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60000)
    return fetch(
      `/api/novel-content?url=${encodeURIComponent(url)}&translate=${translate ? 1 : 0}&${qs(tok())}`,
      { signal: ctrl.signal }
    )
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '内容获取失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  novelChapters: (url) =>
    fetch(`/api/novel-chapters?url=${encodeURIComponent(url)}&${qs(tok())}`).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '目录获取失败')
      return r.json()
    }),
  musicSources: () =>
    fetch('/api/music-sources').then(async (r) => {
      if (!r.ok) throw new Error('音乐源获取失败')
      return r.json()
    }),
  musicSearch: (params) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60000)
    return fetch(`/api/music-search?${qs(params)}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '音乐搜索失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  musicPreviewUrl: (url) => `/api/music-preview?url=${encodeURIComponent(url)}`,
  musicDownloadUrl: (url, filename) =>
    `/api/music-download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(filename || 'music')}`,
  fileProxyUrl: (url) => `/api/file-proxy?url=${encodeURIComponent(url)}`,
  bookSources: () =>
    fetch('/api/book-sources').then(async (r) => {
      if (!r.ok) throw new Error('书源获取失败')
      return r.json()
    }),
  bookSearch: (params) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 90000)
    return fetch(`/api/book-search?${qs(params)}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error || '教材搜索失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  bookDownloadUrl: (url, filename, format) =>
    `/api/book-download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(filename || 'download')}&format=${encodeURIComponent(format || '')}`,
  dsSummarize: (text) =>
    fetch('/api/ds-summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '摘要生成失败')
      return r.json()
    }),
  verify: (code) =>
    fetch(`/api/verify?code=${encodeURIComponent(code)}`).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '激活失败')
      return r.json()
    }),
  issueCode: (adminKey, count = 1) =>
    fetch('/api/issue-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_key: adminKey, count }),
    }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json()).error || '发码失败')
      return r.json()
    }),
  // ---- RuoYi 账号系统占位（后续接入时实现）----
  login: async (_email, _pwd) => ({ ok: false, error: 'RuoYi 接入待开放' }),
  logout: async () => ({ ok: true }),
  getUserInfo: async () => null,
}
