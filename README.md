# 万爬网 / WanpaWeb

多源批量爬取工具（双版本）：图片搜索 + 小说阅读 + 漫画下载 + DeepSeek AI 辅助。
A multi-source batch scraping toolkit (two tiers): image search + novel reader + comic download + DeepSeek AI assistant.

## 双版本 / Two Tiers

- **Lite（免费）**：国内源（bing、pixabay、unsplash 等）+ biquga 小说，无需激活。
  **Lite (free)**: domestic sources + biquga novels, no activation needed.
- **Plus（付费）**：全量源（含海外、hhe62、漫画、pixiv 等），需激活码。
  **Plus (paid)**: all sources (overseas, hhe62, comics, pixiv, etc.), requires activation code.

激活码格式 `WANPA-XXXX-XXXX-XXXX`，通过 `api/issue-code.py` 生成、`api/verify.py` 验证并签发 token。
Activation codes are formatted `WANPA-XXXX-XXXX-XXXX`, issued via `api/issue-code.py` and verified via `api/verify.py` to mint a token.

## 功能 / Features

- **图片搜索**：多源聚合搜索，支持自定义 URL 批量下载
  **Image search**: aggregated search across multiple sources, custom URL batch download
- **小说阅读**：笔趣阁（Lite）+ hhe62（Plus）多源搜索、章节阅读、批量下载
  **Novel reader**: multi-source search (biquga Lite + hhe62 Plus), chapter reading and batch download
- **漫画下载**：14 个漫画源，支持封面预览与整本下载（Plus）
  **Comic download**: 14 comic sources with cover preview and whole-comic download (Plus)
- **DeepSeek AI**：内容摘要、结果过滤、文本清洗（需自备 `DEEPSEEK_KEY`）
  **DeepSeek AI**: content summarization, result filtering, text cleaning (requires your own `DEEPSEEK_KEY`)

## 技术栈 / Tech Stack

- 前端 / Frontend：Vue 3 + Vite（构建产物在 `public/`）
- 后端 / Backend：Python 无框架 serverless handlers（`api/`）
- 部署 / Deploy：Vercel（`vercel.json` 已配置 Serverless Functions + SPA 重写）

## 本地运行 / Run Locally

```bash
# 1. 构建前端（输出到 public/） / Build frontend (output to public/)
cd frontend
npm install
npm run build

# 2. 一键启动本地服务（端口 7732） / Start local server (port 7732)
start.bat
# or
python local_server.py
```

打开 `http://localhost:7732`。

## 部署到 Vercel / Deploy to Vercel

1. 将本仓库导入 Vercel（Framework Preset 选 Other，Build Command 留空）
   Import this repo to Vercel (Framework Preset: Other, leave Build Command empty)
2. 在 Vercel 中启用 KV（Store → KV → Create），获取 REST URL 与 Token
   Enable Vercel KV (Store → KV → Create) and grab the REST URL and token
3. 环境变量 / Environment variables（Vercel → Settings → Environment Variables）:
   - `KV_REST_API_URL`：Vercel KV REST URL（激活码持久化需要，不配则回退本地内存，重启丢失）
     Vercel KV REST URL (required to persist activation codes; falls back to in-memory otherwise)
   - `KV_REST_API_TOKEN`：Vercel KV REST Token
     Vercel KV REST Token
   - `WANPA_ADMIN_KEY`：发码接口管理密钥（`POST /api/issue-code` 鉴权用）
     Admin key for `POST /api/issue-code`
   - `WANPA_PLUS_SECRET`：可选，token 签发密钥（不配使用默认值）
     Optional token signing secret
   - `WANPA_MASTER_CODE`：可选，管理员主激活码（逗号分隔，永久有效）
     Optional master activation codes (comma separated, permanent)
   - `PROXY`：爬虫代理地址，格式 `http://user:pass@host:port`
     Crawler proxy URL, format `http://user:pass@host:port`
   - `DEEPSEEK_KEY`：DeepSeek API Key（AI 功能需要，可留空自动降级）
     DeepSeek API Key (required for AI features, can be left empty to auto-degrade)
   - `PIXIV_PHPSESSID`：Pixiv 源需要，格式 `12345678_xxxx...`
     Pixiv PHPSESSID cookie
   - `PEXELS_KEY`：Pexels API Key（不配则退回 HTML 爬取，云端可能被 403）
     Pexels API Key (falls back to HTML scraping which may be blocked on Vercel)
   - `UNSPLASH_KEY`：Unsplash API Access Key（不配则被源站防护墙拦截）
     Unsplash API Access Key (required, otherwise blocked by the source firewall)
   - `JAMENDO_CLIENT_ID`：Jamendo 音乐源 Client ID（不配则该源返回空）
     Jamendo music Client ID (required for the Jamendo source)
   - `PIXABAY_KEY`：可选，Pixabay API Key（不配也能用，但有配额）
     Optional Pixabay API Key (works without, but rate-limited)
   - `GOOGLE_BOOKS_KEY`：可选，Google Books API Key（不配也能用，但有配额）
     Optional Google Books API Key (works without, but rate-limited)
   - `MACCMS_BASE`：可选，hhe62 服务地址覆盖（默认 `https://zfxdrshm.top:2549`）
     Optional override for the maccms service base URL
4. 部署后访问线上地址即可 / Visit the deployed URL after deployment

> 注意：所有 Plus 接口（`/api/search` 的 plus 源、`/api/comic-*`、`/api/novel-*` 的 hhe62 分支）
> 均要求 token。token 通过 `GET /api/verify?code=WANPA-XXXX-XXXX-XXXX` 获得。
> Note: all Plus endpoints require a token obtained from `GET /api/verify?code=WANPA-XXXX-XXXX-XXXX`.

## 环境变量 / 密钥配置指南（Environment Variables Guide）

### 本地开发 / Local development

本地运行时（`python local_server.py`），配置写在项目根目录的 `.env` 或 `.env.local`
（`.env.local` 优先级更高，两者均已被 `.gitignore` 忽略，不会提交）。
格式为每行 `KEY=value`：

```ini
# 爬虫代理：Clash / V2rayN 等本地代理端口
PROXY=http://127.0.0.1:7897

# DeepSeek AI 密钥（在 platform.deepseek.com 注册获取）
DEEPSEEK_KEY=sk-xxxxxxxxxxxxxxxx

# Pixiv cookie（见下方获取方法）
PIXIV_PHPSESSID=12345678_xxxxxxxx
```

> 代理只对"海外源"生效。国内源（bing / baidu / 360 / 堆糖 / 秀人 / 笔趣阁等）使用直连，
> 不走代理，因此在国内网络下也能正常使用。

### Vercel 云端 / On Vercel

云端请把**同一组变量**填到 `Vercel → Settings → Environment Variables` 后 Redeploy。
`PROXY` 在云端必须是**公网可达的代理**（不能是 `127.0.0.1`），
例如自建 VPS 上的 HTTP 代理、或机场服务商提供的 HTTP/SOCKS 代理出口。
没有公网代理时，海外源（Yahoo / Pexels / Pixiv / 海外小说与漫画源等）在云端无法稳定访问。

### 各密钥获取方法 / How to obtain each key

| 变量 | 用途 | 获取方法 |
| --- | --- | --- |
| `PROXY` | 爬虫代理（海外源） | 本地：Clash/V2rayN 的混合端口；云端：自建 VPS 或机场 HTTP 代理 |
| `DEEPSEEK_KEY` | AI 摘要/过滤/清洗 | 打开 `https://platform.deepseek.com` → 注册/登录 → 左侧「API Keys」→「创建 API Key」→ 复制 `sk-...` |
| `PIXIV_PHPSESSID` | Pixiv 图片源 | 电脑浏览器登录 `https://www.pixiv.net`（保持登录）→ 按 F12 打开开发者工具 → Network 标签 → 刷新页面 → 任选一个请求 → Headers → Cookie → 找到 `PHPSESSID=xxxx`，复制等号后的值 |
| `PEXELS_KEY` | Pexels 图库 | 打开 `https://www.pexels.com/api/` → 注册/登录 → 「Your API Key」→ 生成并复制 |
| `UNSPLASH_KEY` | Unsplash 图库 | 打开 `https://unsplash.com/developers` → 注册/登录 → 「Your apps」→「New application」同意协议 → 复制 Access Key |
| `JAMENDO_CLIENT_ID` | Jamendo 音乐 | 打开 `https://devportal.jamendo.com/` → 注册/登录 → 「Your Apps」→「Create app」→ 复制 Client ID |
| `PIXABAY_KEY` | Pixabay 图库（可选） | 打开 `https://pixabay.com/api/docs/` → 注册/登录 → 右侧即可看到你的 API Key |
| `GOOGLE_BOOKS_KEY` | Google Books（可选） | 打开 `https://console.cloud.google.com/apis/library/books.googleapis.com` → 启用 Google Books API → 凭据 → 创建 API Key |
| `MACCMS_BASE` | hhe62 源 | 一般无需配置，默认 `https://zfxdrshm.top:2549` |

### 配置后效果 / Effect after configuration

- 未配置 `UNSPLASH_KEY`：Unsplash 源被源站防护墙拦截，返回错误（而非空结果）。
- 未配置 `JAMENDO_CLIENT_ID`：音乐源列表不显示 Jamendo。
- 未配置 `PIXIV_PHPSESSID`：Pixiv 源提示配置。
- 未配置 `PEXELS_KEY`：Pexels 退回 HTML 爬取，Vercel 云端易被 403。
- 配置 `PROXY`（公网）后：Yahoo、Pexels、Pixiv、海外小说/漫画源均可稳定访问。

## 目录结构 / Project Structure

```
api/          后端函数（search / novel / comic / verify / issue-code 等） Serverless functions
api/_auth.py  激活码签发、token 校验、Plus 源判定 Activation auth
api/_kv.py    Vercel KV 封装（含内存回退） KV wrapper (in-memory fallback)
frontend/     前端源码（Vue3 + Vite） Frontend source code
public/       前端构建产物（Vercel 静态文件） Frontend build output
vercel.json   Vercel 配置 Vercel config
local_server.py / start.bat  本地一键启动 One-click local start
```

## 激活码接口 / Activation API

| 接口 / Endpoint | 方法 / Method | 说明 / Description |
| --- | --- | --- |
| `/api/verify?code=...` | GET | 验证激活码并签发 token / verify code, mint token |
| `/api/issue-code` | POST | 生成激活码，需 `{"admin_key","count"}` / issue codes, requires admin key |

## 免责声明 / Disclaimer

本工具仅供学习与个人使用，请遵守相关法律法规，尊重网站版权与 robots 协议。
This tool is for learning and personal use only. Please comply with laws and regulations and respect website copyrights and robots protocols.
