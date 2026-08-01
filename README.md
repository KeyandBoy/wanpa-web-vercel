# 万爬网 wanpaweb

绿色健康版多源批量爬取工具：图片搜索 + 小说阅读 + DeepSeek AI 辅助。

## 功能

- **图片搜索**：多源聚合搜索，支持自定义 URL 批量下载
- **小说阅读**：笔趣阁多源搜索、章节阅读、批量下载
- **DeepSeek AI**：内容摘要、结果过滤、文本清洗（需自备 `DEEPSEEK_KEY`）

## 技术栈

- 前端：Vue 3 + Vite（构建产物在 `public/`）
- 后端：Python 无框架 serverless handlers（`api/`）
- 部署：Vercel（`vercel.json` 已配置 Serverless Functions + SPA 重写）

## 本地运行

```bash
# 1. 构建前端（输出到 public/）
cd frontend
npm install
npm run build

# 2. 一键启动本地服务（端口 7732）
start.bat
# 或
python local_server.py
```

打开 `http://localhost:7732`。

## 部署到 Vercel

1. 将本仓库导入 Vercel（Framework Preset 选 Other，Build Command 留空）
2. 环境变量：
   - `DEEPSEEK_KEY`：DeepSeek API Key（AI 功能需要，可留空，AI 接口会自动降级）
   - `PROXY`：可选，爬虫代理地址，格式 `http://user:pass@host:port`
3. 部署后访问线上地址即可

## 目录结构

```
api/          后端 Serverless 函数（search / novel / proxy / ds-* 等）
frontend/     前端源码（Vue3 + Vite）
public/       前端构建产物（Vercel 静态文件）
vercel.json   Vercel 配置
local_server.py / start.bat  本地一键启动
```

## 免责声明

本工具仅供学习与个人使用，请遵守相关法律法规，尊重网站版权与 robots 协议。
