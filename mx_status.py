"""mx_status.py — 统一 MX/DNS 投递状态模块（P7）。

唯一状态枚举（全生产树只允许这一套状态名）：
  mx_pass             — 存在 MX 记录，可正常投递
  implicit_mail_route — 无 MX 但有 A/AAAA，RFC5321 隐式投递路由（不算 fail）
  null_mx             — Null MX（显式拒收，. 记录）
  nxdomain            — 域名不存在
  no_mail_route       — 无 MX 且无 A/AAAA 且无错误，无法投递
  timeout             — 原始 DNS 超时错误名（保留枚举位）
  servfail            — SERVFAIL（重试语义）
  retry_pending       — 超时 / 网络错误（重试语义，绝不能转成 nxdomain）

权威函数：
  mx_status_from_dns(has_mx, has_a, has_aaaa, is_null_mx, error_type) -> str

判定顺序（关键语义）：
  1. 超时 / 网络错误 → retry_pending（绝不能 timeout→nxdomain）
  2. SERVFAIL → servfail
  3. NXDOMAIN → nxdomain
  4. 存在 MX：
       - Null MX（is_null_mx）→ null_mx
       - 否则 → mx_pass
  5. 无 MX 但 is_null_mx → null_mx
  6. 无 MX 但有 A 或 AAAA → implicit_mail_route
  7. 无 MX 无 A 无 AAAA 且无错误 → no_mail_route
"""

# ── 唯一状态枚举 ─────────────────────────────────────────────
MX_PASS = "mx_pass"
IMPLICIT_MAIL_ROUTE = "implicit_mail_route"
NULL_MX = "null_mx"
NXDOMAIN = "nxdomain"
NO_MAIL_ROUTE = "no_mail_route"
TIMEOUT = "timeout"
SERVFAIL = "servfail"
RETRY_PENDING = "retry_pending"

ALL_STATUSES = frozenset({
    MX_PASS, IMPLICIT_MAIL_ROUTE, NULL_MX, NXDOMAIN,
    NO_MAIL_ROUTE, TIMEOUT, SERVFAIL, RETRY_PENDING,
})

# 判定为可投递的状态（供上层门禁直接复用）
DELIVERABLE_STATUSES = frozenset({MX_PASS, IMPLICIT_MAIL_ROUTE})

# 判定为"需要稍后重试"的状态（不视为永久失败）
RETRYABLE_STATUSES = frozenset({TIMEOUT, SERVFAIL, RETRY_PENDING})

# 错误名 → 状态映射（大小写不敏感）
_ERROR_TYPE_MAP = {
    "timeout": RETRY_PENDING,
    "dns_timeout": RETRY_PENDING,
    "timedout": RETRY_PENDING,
    "timed_out": RETRY_PENDING,
    "network_error": RETRY_PENDING,
    "network": RETRY_PENDING,
    "econnrefused": RETRY_PENDING,
    "econnreset": RETRY_PENDING,
    "connectionerror": RETRY_PENDING,
    "eai_again": RETRY_PENDING,       # 临时解析失败
    "servfail": SERVFAIL,
    "serverfailure": SERVFAIL,
    "dns_servfail": SERVFAIL,
    "nxdomain": NXDOMAIN,
    "nx_domain": NXDOMAIN,
    "noanswer": NO_MAIL_ROUTE,
    "no_mx": NO_MAIL_ROUTE,
    "nodata": NO_MAIL_ROUTE,
}


def mx_status_from_dns(has_mx: bool, has_a: bool, has_aaaa: bool,
                       is_null_mx: bool = False, error_type: str | None = None) -> str:
    """把一次 DNS 查询结果归一化为唯一投递状态。

    参数：
      has_mx    — 域名是否存在 MX 记录
      has_a     — 是否存在 A 记录
      has_aaaa  — 是否存在 AAAA 记录
      is_null_mx— 是否 Null MX（存在但为 "." 的拒收记录）
      error_type— 原始错误名（如 "timeout" / "SERVFAIL" / "NXDOMAIN" / None）

    返回：ALL_STATUSES 中的唯一状态名。
    """
    err = (error_type or "").strip().lower()

    # 1. 超时 / 网络错误 → retry_pending（绝不能转成 nxdomain）
    if err in _ERROR_TYPE_MAP:
        return _ERROR_TYPE_MAP[err]

    # 2. 有显式错误但未识别 → 按重试语义处理，避免误判为永久失败
    if err:
        return RETRY_PENDING

    # 3. 存在 MX 记录
    if has_mx:
        return NULL_MX if is_null_mx else MX_PASS

    # 4. Null MX 优先级高于 A/AAAA（显式拒收）
    if is_null_mx:
        return NULL_MX

    # 5. 无 MX 但有 A 或 AAAA → 隐式投递路由
    if has_a or has_aaaa:
        return IMPLICIT_MAIL_ROUTE

    # 6. 无 MX 无 A 无 AAAA 且无错误
    return NO_MAIL_ROUTE
