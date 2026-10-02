import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import classify_error, err_json, ok_json

# 播放端点：HLS 走 playlist 改写，其余走带 Range 的直链代理
_HLS_MARKERS = (".m3u8", "m3u8?")


def _play_url(cand):
    u = cand.get("url") or ""
    if not u:
        return ""
    kind = (cand.get("kind") or "").lower()
    is_hls = kind == "hls" or any(m in u.lower() for m in _HLS_MARKERS)
    from stream_sign import sign

    endpoint = "/api/hls-playlist" if is_hls else "/api/video-preview"
    return "%s?url=%s&sig=%s" % (endpoint, quote(u, safe=""), sign(u))


def _sign_candidates(result):
    """给解析结果附上签名，供前端拼接播放地址。

    播放类接口是开放代理，没有签名就会被当免费代理白嫖流量；签名由
    stream_sign 生成并自带过期时间。

    前端契约（见 frontend/src/api.js）用的是**顶层 `url`**（不是
    candidates），所以顶层 `sig` 才是主路径；DASH 站的音频流另走顶层
    `audio_url` + `audio_sig`，由双元素播放器同步；`candidates[].play_url`
    是给直接按候选消费的调用方用的完整相对地址。
    """
    from stream_sign import sign

    for cand in result.get("candidates") or []:
        cand["play_url"] = _play_url(cand)
    for key in ("url", "audio_url"):
        top = result.get(key)
        if not top:
            continue
        result["sig" if key == "url" else "audio_sig"] = sign(top)
    return result


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        url = (qs.get("url") or [""])[0].strip()
        mode = (qs.get("mode") or ["auto"])[0].strip() or "auto"
        if not url:
            body, headers, status = err_json(400, "url 参数不能为空")
        elif mode not in ("auto", "ytdlp", "server", "browser"):
            body, headers, status = err_json(400, "mode 只能是 auto/ytdlp/server/browser")
        elif mode == "browser":
            # Vercel 无浏览器环境，S3.5 已整体移除
            body, headers, status = err_json(400, "本部署未启用浏览器解析，请改用 mode=auto")
        else:
            try:
                info = None
                # 51 吃瓜的帖子是 HLS 流，优先走站点专用解析
                if mode in ("auto", "ytdlp"):
                    try:
                        from cg51_svc import is_post_url, post_video

                        if is_post_url(url):
                            info = post_video(url)
                    except Exception:
                        info = None
                if info is None:
                    from video_svc import resolve_video

                    info = resolve_video(url, mode=mode)
                body, headers = ok_json(_sign_candidates(info))
                status = 200
            except Exception as e:
                body, headers, status = err_json(500, str(e), error_type=classify_error(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
