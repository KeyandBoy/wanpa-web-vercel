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
3. 环境变量 / Environment variables:
   - `KV_REST_API_URL`：Vercel KV REST URL（激活码持久化需要，不配则回退本地内存，重启丢失）
     Vercel KV REST URL (required to persist activation codes; falls back to in-memory otherwise)
   - `KV_REST_API_TOKEN`：Vercel KV REST Token
     Vercel KV REST Token
   - `WANPA_ADMIN_KEY`：发码接口管理密钥（`POST /api/issue-code` 鉴权用）
     Admin key for `POST /api/issue-code`
   - `WANPA_PLUS_SECRET`：可选，token 签发密钥（不配使用默认值）
     Optional token signing secret
   - `DEEPSEEK_KEY`：DeepSeek API Key（AI 功能需要，可留空自动降级）
     DeepSeek API Key (required for AI features, can be left empty to auto-degrade)
   - `PROXY`：可选，爬虫代理地址，格式 `http://user:pass@host:port`
     Optional crawler proxy, format `http://user:pass@host:port`
   - `PIXIV_PHPSESSID`：可选，Pixiv 源需要，格式 `12345678_xxxx...`
     Optional Pixiv PHPSESSID cookie
   - `MACCMS_BASE`：可选，hhe62 服务地址覆盖（默认 `https://zfxdrshm.top:2549`）
     Optional override for the maccms service base URL
4. 部署后访问线上地址即可 / Visit the deployed URL after deployment

> 注意：所有 Plus 接口（`/api/search` 的 plus 源、`/api/comic-*`、`/api/novel-*` 的 hhe62 分支）
> 均要求 token。token 通过 `GET /api/verify?code=WANPA-XXXX-XXXX-XXXX` 获得。
> Note: all Plus endpoints require a token obtained from `GET /api/verify?code=WANPA-XXXX-XXXX-XXXX`.

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
