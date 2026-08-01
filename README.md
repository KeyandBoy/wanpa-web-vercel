# 万爬网 / WanpaWeb

绿色健康版多源批量爬取工具：图片搜索 + 小说阅读 + DeepSeek AI 辅助。
A clean multi-source batch scraping toolkit: image search + novel reader + DeepSeek AI assistant.

## 功能 / Features

- **图片搜索**：多源聚合搜索，支持自定义 URL 批量下载
  **Image search**: aggregated search across multiple sources, custom URL batch download
- **小说阅读**：笔趣阁多源搜索、章节阅读、批量下载
  **Novel reader**: multi-source search, chapter reading and batch download
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
2. 环境变量 / Environment variables:
   - `DEEPSEEK_KEY`：DeepSeek API Key（AI 功能需要，可留空自动降级）
     DeepSeek API Key (required for AI features, can be left empty to auto-degrade)
   - `PROXY`：可选，爬虫代理地址，格式 `http://user:pass@host:port`
     Optional crawler proxy, format `http://user:pass@host:port`
3. 部署后访问线上地址即可 / Visit the deployed URL after deployment

## 目录结构 / Project Structure

```
api/          后端函数（search / novel / proxy / ds-* 等） Serverless functions
frontend/     前端源码（Vue3 + Vite） Frontend source code
public/       前端构建产物（Vercel 静态文件） Frontend build output
vercel.json   Vercel 配置 Vercel config
local_server.py / start.bat  本地一键启动 One-click local start
```

## 免责声明 / Disclaimer

本工具仅供学习与个人使用，请遵守相关法律法规，尊重网站版权与 robots 协议。
This tool is for learning and personal use only. Please comply with laws and regulations and respect website copyrights and robots protocols.
