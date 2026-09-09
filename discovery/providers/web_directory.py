"""WebDirectoryProvider — 无 API key 的自动新商户发现源。

从公开游戏/爱好店目录站抓取 TN/AR/KY 的独立零售店（店名、城市、州、
电话、部分官网），作为 Google Places/SerpAPI 不可用时的自动 Discovery 层。

数据源（免费、公开、结构化 HTML）：
  - wargames.com/directory/{Tennessee,Kentucky,Arkansas}  — 桌游/战棋店目录
  - localgamestores.com 对应州页  — 本地游戏店目录（作为扩展源）

设计约束：
  * 只做「新商户发现」，返回 PlaceSearchResult（含店名/地址/电话/官网）。
  * 邮箱/官网验证由下游 inventory 官网扫描负责（provider 不抓邮箱）。
  * 网络失败 → ProviderPage(status='provider_timeout'/'provider_error')，
    绝不把网络错误当"无结果"。
  * configured=True：不依赖任何 API key。
"""
from __future__ import annotations

import re
import urllib.request
import urllib.error

from discovery.models import PlaceSearchResult, ProviderPage
from discovery.providers.base import SearchProvider

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RoktAndRazoBDDiscovery/1.0"

# 目录页 → 州代码
_DIRECTORY_PAGES = {
    "TN": "http://www.wargames.com/directory/Tennessee",
    "KY": "http://www.wargames.com/directory/Kentucky",
    "AR": "http://www.wargames.com/directory/Arkansas",
    "AL": "http://www.wargames.com/directory/Alabama",
    "GA": "http://www.wargames.com/directory/Georgia",
    "VA": "http://www.wargames.com/directory/Virginia",
    "MO": "http://www.wargames.com/directory/Missouri",
    "MS": "http://www.wargames.com/directory/Mississippi",
    "IN": "http://www.wargames.com/directory/Indiana",
    "OH": "http://www.wargames.com/directory/Ohio",
    "IL": "http://www.wargames.com/directory/Illinois",
    "OK": "http://www.wargames.com/directory/Oklahoma",
    "LA": "http://www.wargames.com/directory/Louisiana",
    "FL": "http://www.wargames.com/directory/Florida",
    "NC": "http://www.wargames.com/directory/North-Carolina",
    "SC": "http://www.wargames.com/directory/South-Carolina",
}

# 店块结构：<p class="directorystore"> <span class="directorystorename"><a href="...">NAME</a>
# <span class="directorystorephone">PHONE <span class="directorystorelocation">CITY, STATE ZIP
_STORE_BLOCK_RE = re.compile(
    r'<p class="directorystore">(.*?)</p>', re.IGNORECASE | re.DOTALL
)
_NAME_RE = re.compile(
    r'class="directorystorename"><a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL
)
_PHONE_RE = re.compile(r'class="directorystorephone">(.*?)<br', re.IGNORECASE | re.DOTALL)
_LOC_RE = re.compile(r'class="directorystorelocation">(.*?)<br', re.IGNORECASE | re.DOTALL)


def _strip(tag_text: str) -> str:
    """HTML 片段 → 干净文本。"""
    if not tag_text:
        return ""
    t = re.sub(r"<[^>]+>", "", tag_text)
    t = t.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    return re.sub(r"\s+", " ", t).strip()


def _parse_location(loc_text: str, default_state: str) -> tuple[str, str]:
    """'Bowling Green, Kentucky 42101' → ('Bowling Green', 'KY')。"""
    t = _strip(loc_text)
    if not t:
        return "", default_state
    city = ""
    state_code = default_state
    m = re.match(r"^(.*?),\s*([A-Za-z\s]+?)\s*\d{4,5}$", t)
    if m:
        city = m.group(1).strip()
        state_full = m.group(2).strip()
        # 常见全称→缩写
        state_map = {
            "Tennessee": "TN", "Kentucky": "KY", "Arkansas": "AR",
            "Alabama": "AL", "Georgia": "GA", "Virginia": "VA",
            "Missouri": "MO", "Mississippi": "MS", "Illinois": "IL",
            "Indiana": "IN", "Ohio": "OH", "North Carolina": "NC",
            "South Carolina": "SC", "Texas": "TX", "California": "CA",
            "New York": "NY", "Pennsylvania": "PA", "Michigan": "MI",
            "Florida": "FL", "Louisiana": "LA", "Oklahoma": "OK",
        }
        state_code = state_map.get(state_full.title(), default_state)
    elif "," in t:
        parts = t.split(",")
        city = parts[0].strip()
        if len(parts) > 1:
            state_code = _strip(parts[1]).split()[0].upper() or default_state
    else:
        city = t
    return city, state_code


class WebDirectoryProvider(SearchProvider):
    """抓取公开目录站的自动新商户发现源（无 API key）。"""

    provider_name = "web_directory"

    def __init__(self, timeout: float = 20.0, page_size: int = 50) -> None:
        self.timeout = timeout
        self.page_size = page_size

    @property
    def configured(self) -> bool:
        return True  # 不依赖外部 key，始终可用

    def _fetch(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def search_places(
        self,
        query: str,
        city: str,
        state: str,
        page_cursor: str = "",
        page_size: int = 20,
    ) -> ProviderPage:
        # state 用于选目录页；page_cursor 支持按序翻页（简单实现：cursor 为空=第1页，
        # 返回全部结果后 next 为空，query 完成）
        page_url = _DIRECTORY_PAGES.get(state.upper())
        if not page_url:
            return ProviderPage(
                provider=self.provider_name, query=query, city=city, state=state,
                page_cursor=page_cursor,
                status="provider_not_configured",
                error=f"no directory page for state {state}",
            )
        try:
            html = self._fetch(page_url)
        except urllib.error.HTTPError as e:
            return ProviderPage(
                provider=self.provider_name, query=query, city=city, state=state,
                page_cursor=page_cursor, status="provider_error",
                error=f"http_{e.code}",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return ProviderPage(
                provider=self.provider_name, query=query, city=city, state=state,
                page_cursor=page_cursor, status="provider_timeout",
                error=f"network_error: {str(e)[:80]}",
            )

        results: list[PlaceSearchResult] = []
        for block in _STORE_BLOCK_RE.findall(html):
            m_name = _NAME_RE.search(block)
            if not m_name:
                continue
            link, name = m_name.group(1), _strip(m_name.group(2))
            if not name:
                continue
            m_loc = _LOC_RE.search(block)
            store_city, store_state = _parse_location(
                m_loc.group(1) if m_loc else "", state.upper()
            )
            m_phone = _PHONE_RE.search(block)
            phone = _strip(m_phone.group(1)) if m_phone else ""
            website = link if link.startswith("http") else ("http://www.wargames.com" + link if link.startswith("/") else "")
            results.append(
                PlaceSearchResult(
                    provider=self.provider_name,
                    provider_result_id=f"wgdir-{state}-{name.lower()[:60].replace(' ', '-')}",
                    place_id=f"wgdir-{state}-{len(results)}",
                    business_name=name,
                    formatted_address=f"{store_city}, {store_state}" if store_city else f", {state.upper()}",
                    city=store_city,
                    state=store_state,
                    phone=phone,
                    website="",  # 目录详情页不是商户官网；官网由 inventory 扫描补
                    business_status="OPERATIONAL",
                    primary_type="store",
                    types=["store", "game_store"],
                    source_query=query,
                    source_url=page_url,
                    raw_payload={"directory": "wargames.com"},
                )
            )

        if not results:
            return ProviderPage(
                provider=self.provider_name, query=query, city=city, state=state,
                page_cursor=page_cursor, status="provider_no_results",
                error="no store blocks parsed",
            )

        return ProviderPage(
            provider=self.provider_name,
            query=query,
            city=city,
            state=state,
            page_cursor=page_cursor,
            results=results,
            next_page_cursor="",
            status="ok",
            request_count=1,
        )

    def search_web_directories(
        self,
        city: str,
        state: str,
        query_family: str,
        cursor: str = "",
    ) -> ProviderPage:
        # 本项目 web_directory 本身即目录源，走同一条抓取逻辑
        return self.search_places(query_family, city, state, cursor)
