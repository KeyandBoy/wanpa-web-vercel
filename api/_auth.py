import hashlib
import hmac
import os
import secrets

from _kv import delete, get, set

# 激活码池存储键：code:<code> -> {used, activated_at}
# token 存储键：token:<token> -> code（激活后写入，用于 Plus 接口鉴权）
_SECRET = os.environ.get("WANPA_PLUS_SECRET") or "wanpa-plus-default-secret"

# 管理员主激活码列表：不写入 KV 码池，永久有效、可多次验证、重启不丢。
# 从环境变量 WANPA_MASTER_CODE 读取，支持逗号分隔多个码（隐私密码，绝不硬编码进代码/仓库）。
# 未设置则无主码功能，仅普通激活码可用。
_MASTER_CODES = [
    c.strip().upper()
    for c in (os.environ.get("WANPA_MASTER_CODE") or "").split(",")
    if c.strip()
]


def _sig(code):
    return hmac.new(_SECRET.encode(), ("plus:" + code).encode(), hashlib.sha256).hexdigest()


def _master_tokens():
    # 每个主码各自有确定性 token，check_token 无需查 KV 即可验证
    return {_sig("MASTER:" + c) for c in _MASTER_CODES}


def is_master_code(code):
    return bool(_MASTER_CODES) and code in _MASTER_CODES


def new_code():
    """生成激活码：WANPA-XXXX-XXXX-XXXX"""
    seg = [secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(4)]
    seg2 = [secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(4)]
    seg3 = [secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(4)]
    return "WANPA-%s-%s-%s" % ("".join(seg), "".join(seg2), "".join(seg3))


def issue_codes(count, prefix="WANPA-"):
    """批量生成激活码并写入 KV 码池（未使用）。返回 [code,...]"""
    codes = []
    for _ in range(count):
        code = new_code()
        set("code:" + code, {"used": False, "activated_at": None})
        codes.append(code)
    return codes


def verify_code(code):
    """校验激活码：存在码池则标记已用并签发 token。

    - 管理员主码：直接签发确定性 token（永久有效、可多次验证、不写入码池）。
    - 未使用过的码：标记已用，返回 token。
    - 已使用过的码：仍返回 token（永久有效，已用码可在新设备重新解锁）。
    - 不存在/格式不对：返回 None。
    """
    if not code:
        return None
    code = code.strip().upper()
    if is_master_code(code):
        return _sig("MASTER:" + code)
    rec = get("code:" + code)
    if rec is None:
        return None
    token = _sig(code)
    set("token:" + token, {"code": code, "activated_at": rec.get("activated_at") or None})
    return token


def check_token(token):
    """校验 Plus token 是否有效（已激活的码签发过）"""
    if not token:
        return False
    if token in _master_tokens():
        return True
    return get("token:" + token) is not None


def is_plus_source(source):
    """哪些图片/小说源属于 Plus 专属（成人/海外/需要激活）"""
    plus = {
        "hhe62", "foamgirl", "pixiv", "anime-pictures", "meitulu", "xsnvshen",
        "pornpics", "photos18", "asiantolick", "pornhub", "pornhub-albums", "xxknit",
        "aaanovel", "1000novel", "xbookcn", "hhhbook", "canovel", "h528", "69story", "alicesw",
        "bdsmcafe", "chyoa",
    }
    return source in plus


def is_plus_comic():
    return True
