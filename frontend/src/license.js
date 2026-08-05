import { reactive } from 'vue'

const LS_KEY = 'wanpa-license'

function load() {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return null
    const d = JSON.parse(raw)
    if (d && d.version === 'plus' && d.token) return d
    return null
  } catch (e) {
    return null
  }
}

export const license = reactive({
  version: 'lite',
  token: '',
  code: '',
  loaded: false,
})

export function initLicense() {
  const d = load()
  if (d) {
    license.version = d.version
    license.token = d.token
    license.code = d.code || ''
  }
  license.loaded = true
}

export function setPlus(token, code) {
  license.version = 'plus'
  license.token = token
  license.code = code || ''
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({ version: 'plus', token, code }))
  } catch (e) {}
}

export function resetLicense() {
  license.version = 'lite'
  license.token = ''
  license.code = ''
  try {
    localStorage.removeItem(LS_KEY)
  } catch (e) {}
}

// 当前有效 token（供 api 请求附加）
export function currentToken() {
  return license.version === 'plus' ? license.token : ''
}
