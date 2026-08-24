import os
import re

import requests

try:
    from env_utils import proxies as _proxies
except Exception:
    def _proxies():
        return None


def _key():
    k = os.environ.get("DEEPSEEK_KEY") or ""
    if k and not k.startswith("sk-在这里"):
        return k
    try:
        from env_utils import env as _env

        k2 = _env("DEEPSEEK_KEY", "")
        return k2 if k2 and not k2.startswith("sk-在这里") else None
    except Exception:
        return None


def available():
    return bool(_key())


def chat(system, user, max_tokens=800, temperature=0.7):
    key = _key()
    if not key:
        raise ValueError("未配置 DEEPSEEK_KEY（请在 Vercel 环境变量设置）")
    r = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        },
        timeout=50,
        proxies=_proxies(),
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def summarize(text, max_len=3000):
    if not available():
        raise ValueError("未配置 DEEPSEEK_KEY")
    return chat(
        "你是一个小说内容助手。根据用户提供的小说开头内容，用中文给出简短的简介（2-3句）和可能的类型标签（用逗号分隔）。",
        text[:max_len],
        max_tokens=200,
        temperature=0.3,
    )


def filter_items(keyword, items):
    if not available():
        raise ValueError("未配置 DEEPSEEK_KEY")
    if not items:
        return []
    lines = []
    for it in items:
        title = (it.get("title") or "").strip().replace("\n", " ")
        extra = it.get("extra") or ""
        desc = f"{title}" + (f" | {extra}" if extra else "")
        lines.append(f"{it.get('id')}\t{desc}")
    prompt = (
        "下面是爬虫抓取到的候选内容列表（每行格式：ID<TAB>标题|附加信息）。"
        "请根据用户需求关键词判断每条是否相关，过滤掉：与主题无关、明显是广告/导航/简介页、标题残缺或不完整的条目。"
        "只输出需要保留的 ID，每行一个，不要任何其他文字。\n\n"
        f"需求关键词：{keyword}\n\n候选列表：\n" + "\n".join(lines)
    )
    out = chat(
        "你是内容筛选助手。严格按照用户提供的候选列表和关键词，判断相关性后输出保留的 ID 列表。",
        prompt,
        max_tokens=len(items) * 8 + 60,
        temperature=0.1,
    )
    ids = set()
    for tok in re.split(r"[\s,，、;；]+", out):
        tok = tok.strip()
        if tok.isdigit():
            ids.add(int(tok))
    if not ids:
        return []
    by_id = {it["id"]: it for it in items if "id" in it}
    kept = [by_id[i] for i in ids if i in by_id]
    order = {it["id"]: idx for idx, it in enumerate(items)}
    kept.sort(key=lambda it: order[it["id"]])
    return kept


def clean_content(text, max_len=12000):
    if not available():
        raise ValueError("未配置 DEEPSEEK_KEY")
    if not text or not text.strip():
        return text
    out = chat(
        "你是小说正文清洗助手。用户提供爬取到的小说正文，可能混有广告、站内推广、乱码、重复段落、页脚信息。"
        "请清理这些垃圾内容，保留完整的小说正文段落，不要改变叙事内容和措辞，不要增删情节。"
        "直接输出清洗后的正文，不要任何解释或额外文字。",
        text[:max_len],
        max_tokens=min(len(text[:max_len]) * 2 + 200, 16000),
        temperature=0.1,
    )
    return out
