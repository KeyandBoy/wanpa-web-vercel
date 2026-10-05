import { currentToken } from './license'

const qs = (p) => new URLSearchParams(p).toString()

class ApiError extends Error {
  constructor(msg, errorType) {
    super(msg)
    this.name = 'ApiError'
    this.errorType = errorType || 'unknown'
  }
}

async function throwApiError(r, fallback) {
  try {
    const body = await r.json()
    throw new ApiError(body.error || fallback, body.error_type)
  } catch (e) {
    if (e instanceof ApiError) throw e
    throw new ApiError(fallback, 'unknown')
  }
}

export const isLocal = () =>
  ['localhost', '127.0.0.1', '::1', '[::1]'].includes(location.hostname)

// 附加激活 token（Plus 源请求需要）
const tok = () => {
  const t = currentToken()
  return t ? { token: t } : {}
}

export const api = {
  search: (params, signal) =>
    fetch(`/api/search?${qs({ ...params, ...tok() })}`, { signal }).then(async (r) => {
      if (!r.ok) await throwApiError(r, '搜索失败')
      return r.json()
    }),
  pageImages: (url, signal) =>
    fetch(`/api/page-images?url=${encodeURIComponent(url)}`, { signal }).then(async (r) => {
      if (!r.ok) await throwApiError(r, '网页解析失败')
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
        if (!r.ok) await throwApiError(r, '小说搜索失败')
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
        if (!r.ok) await throwApiError(r, '内容获取失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  novelChapters: (url) =>
    fetch(`/api/novel-chapters?url=${encodeURIComponent(url)}&${qs(tok())}`).then(async (r) => {
      if (!r.ok) await throwApiError(r, '目录获取失败')
      return r.json()
    }),
  novelCategories: () =>
    fetch(`/api/novel-categories?${qs(tok())}`).then(async (r) => {
      if (!r.ok) await throwApiError(r, '分类获取失败')
      return r.json()
    }),
  novelCategory: (params) =>
    fetch(`/api/novel-category?${qs({ ...params, ...tok() })}`).then(async (r) => {
      if (!r.ok) await throwApiError(r, '分类浏览失败')
      return r.json()
    }),
  musicSources: () =>
    fetch('/api/music-sources').then(async (r) => {
      if (!r.ok) await throwApiError(r, '音乐源获取失败')
      return r.json()
    }),
  musicSearch: (params) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60000)
    return fetch(`/api/music-search?${qs(params)}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) await throwApiError(r, '音乐搜索失败')
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
      if (!r.ok) await throwApiError(r, '书源获取失败')
      return r.json()
    }),
  bookSearch: (params) => {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 90000)
    return fetch(`/api/book-search?${qs(params)}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) await throwApiError(r, '教材搜索失败')
        return r.json()
      })
      .finally(() => clearTimeout(timer))
  },
  bookDownloadUrl: (url, filename, format) =>
    `/api/book-download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(filename || 'download')}&format=${encodeURIComponent(format || '')}`,
  // ---- 视频：搜索 / 解析 / 播放 ----
  videoSearch: (params) =>
    fetch(`/api/video-search?${qs({ ...params, ...tok() })}`).then(async (r) => {
      if (!r.ok) await throwApiError(r, '视频搜索失败')
      return r.json()
    }),
  videoResolve: (url, mode) =>
    fetch(
      `/api/video-resolve?url=${encodeURIComponent(url)}${mode ? `&mode=${encodeURIComponent(mode)}` : ''}`
    ).then(async (r) => {
      if (!r.ok) await throwApiError(r, '解析失败')
      return r.json()
    }),
  douyinParse: (url) =>
    fetch(`/api/douyin-parse?url=${encodeURIComponent(url)}`).then(async (r) => {
      if (!r.ok) await throwApiError(r, '抖音解析失败')
      return r.json()
    }),
  // sig 由 /api/video-resolve 返回，必须拼上，否则播放接口一律 403
  videoPreviewUrl: (directUrl, sig) =>
    `/api/video-preview?url=${encodeURIComponent(directUrl)}${sig ? `&sig=${encodeURIComponent(sig)}` : ''}`,
  hlsPlaylistUrl: (m3u8Url, sig) =>
    `/api/hls-playlist?url=${encodeURIComponent(m3u8Url)}${sig ? `&sig=${encodeURIComponent(sig)}` : ''}`,
  hlsSegUrl: (segUrl, sig) =>
    `/api/hls-seg?url=${encodeURIComponent(segUrl)}${sig ? `&sig=${encodeURIComponent(sig)}` : ''}`,
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
