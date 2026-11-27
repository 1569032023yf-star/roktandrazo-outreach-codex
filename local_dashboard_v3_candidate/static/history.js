'use strict';
// Historical Inventory invocations are not equivalent to confirmed searches.
let inventoryHistoryPage = 1;
let cityHistoryPage = 1;
let cityAuditPage = 1;
let cityAuditRequest = 0;
const reportPanel = document.createElement('section');
reportPanel.className = 'panel';
reportPanel.innerHTML = '<h2>旧报告快照（未归属作业）</h2><div id="historical-report-snapshots"></div>';
$('all-inventory-history').parentElement.after(reportPanel);
async function loadHistoricalReports() {
  const node = $('historical-report-snapshots');
  node.innerHTML = '<p class="hint">正在读取旧报告快照…</p>';
  try {
    const result = await api('/api/history-reports');
    if (!result.available) { node.innerHTML = '<p class="error">旧报告目录不可用，数量未知。</p>'; return; }
    const rows = result.items.map(r => `<tr><td>${esc(r.filename)}</td><td>${esc(r.updated_at || '未知')}</td><td>${esc(r.status || '未知')}</td><td>${val(r.candidates_discovered)}</td><td>${val(r.candidates_verified)}</td><td>${val(r.a0_added)}</td></tr>`).join('');
    node.innerHTML = `<p class="hint">${esc(result.scope)} 运行编号、城市和是否模拟均未知。报告数值为原报告自述，可能累计且不可相加；A0 增加不是本轮独立商家数。读取 ${fmt(result.observed_at)}；无法读取 ${result.unreadable} 个文件。</p><div class="table-wrap"><table><thead><tr><th>原始文件</th><th>报告更新时间</th><th>报告状态</th><th>报告称发现候选</th><th>报告称核验候选</th><th>报告称 A0 增加</th></tr></thead><tbody>${rows || '<tr><td colspan="6">没有可显示的报告；不能据此断言没有历史运行。</td></tr>'}</tbody></table></div>`;
  } catch (error) { node.innerHTML = `<p class="error">旧报告读取失败，数量未知：${esc(error.message)}</p>`; }
}
function historyTable(result) {
  const rows = result.items.map(r => `<tr><td>${esc(r.run_id)}${r.log_sources?.length ? '<small>日志：' + r.log_sources.map(esc).join('、') + '</small>' : ''}</td><td>${esc(r.started_at || '暂无记录')}</td><td>${esc(r.finished_at || '暂无记录')}</td><td>${esc(r.kind)} · ${esc(r.status)}</td><td>${r.city_id ? esc(cityName(r.city_id)) : '未知'}<small>${esc(r.city_evidence)}</small></td><td>${r.places_stage_entered ? '有阶段进入回执' : '未知或未进入'}${r.new_places == null ? '' : '<small>日志新增地点：' + val(r.new_places) + '（不等于新增商家）</small>'}</td><td>未知</td></tr>`).join('');
  return `<p class="hint">${esc(result.scope)} 读取时间：${fmt(result.observed_at)}。作业时间保留数据库原文，旧记录时区需核实。新增商家数缺少可靠批次关联，显示未知。</p><div class="table-wrap"><table><thead><tr><th>作业 ID</th><th>开始</th><th>结束</th><th>性质 / 状态</th><th>城市</th><th>发现阶段</th><th>本轮新增商家</th></tr></thead><tbody>${rows || '<tr><td colspan="7">没有可归属的记录，不能据此判断从未运行。</td></tr>'}</tbody></table></div><div class="pagination"><button class="secondary" data-history-prev>上一页</button><span>第 ${result.page} 页 · 可核实作业 ${result.total} 条</span><button class="secondary" data-history-next>下一页</button></div>`;
}
async function loadInventoryHistory(city) {
  const node = city ? $('detail-runs') : $('all-inventory-history');
  if (!node) return;
  const page = city ? cityHistoryPage : inventoryHistoryPage;
  node.innerHTML = '<p class="hint">正在读取历史作业…</p>';
  try {
    const result = await api(`/api/history?page=${page}${city ? '&city=' + encodeURIComponent(city) : ''}`);
    if (city && state.selected !== city) return;
    node.innerHTML = historyTable(result);
    if (city) node.dataset.historyCity = String(city);
    node.querySelector('[data-history-prev]').disabled = page <= 1;
    node.querySelector('[data-history-next]').disabled = page * result.page_size >= result.total;
    node.querySelector('[data-history-prev]').onclick = () => { if (city) cityHistoryPage--; else inventoryHistoryPage--; loadInventoryHistory(city); };
    node.querySelector('[data-history-next]').onclick = () => { if (city) cityHistoryPage++; else inventoryHistoryPage++; loadInventoryHistory(city); };
  } catch (e) {
    node.innerHTML = `<p class="error">历史记录读取失败，数量未知：${esc(e.message)}</p>`;
  }
}
async function loadCityAudit(city) {
  const container = $('detail-queries');
  if (!container || !city) return;
  let node = $('city-audit-history');
  if (!node) { node = document.createElement('div'); node.id = 'city-audit-history'; container.appendChild(node); }
  node.dataset.city = String(city);
  const request = ++cityAuditRequest, page = cityAuditPage;
  node.innerHTML = '<p class="hint">正在读取历史来源审计…</p>';
  try {
    const result = await api(`/api/city-request-audit?city=${encodeURIComponent(city)}&page=${page}`);
    if (request !== cityAuditRequest || state.selected !== city || !node.isConnected) return;
    const rows = result.items.map(r => `<tr><td>${val(r.id)}</td><td>${esc(r.requested_at || '未知')}</td><td>${esc(r.provider || '未知')}</td><td>${esc(r.query_family || '未知')}<small>${esc(r.source_query || '查询内容未记录')}</small></td><td>${esc(r.status || '未知')}</td><td>${val(r.request_count)}</td><td>${val(r.result_count)}</td></tr>`).join('');
    node.innerHTML = `<h3>历史来源审计明细</h3><p class="hint">${esc(result.scope)} 原始时间保留数据库格式；读取时间 ${fmt(result.observed_at)}。${esc(result.source)}。</p><div class="table-wrap"><table><thead><tr><th>记录 ID</th><th>记录时间</th><th>来源</th><th>查询组 / 查询内容</th><th>来源状态</th><th>记录的请求数</th><th>原始结果数</th></tr></thead><tbody>${rows || '<tr><td colspan="7">没有可读审计行，不代表没有历史搜索。</td></tr>'}</tbody></table></div><div class="pagination"><button class="secondary" data-audit-prev>上一页</button><span>第 ${result.page} 页 · ${result.total} 条审计行</span><button class="secondary" data-audit-next>下一页</button></div>`;
    node.querySelector('[data-audit-prev]').disabled = page <= 1;
    node.querySelector('[data-audit-next]').disabled = page * result.page_size >= result.total;
    node.querySelector('[data-audit-prev]').onclick = () => { cityAuditPage--; loadCityAudit(city); };
    node.querySelector('[data-audit-next]').onclick = () => { cityAuditPage++; loadCityAudit(city); };
  } catch (error) {
    if (request === cityAuditRequest && state.selected === city && node.isConnected) node.innerHTML = `<p class="error">历史来源审计读取失败，数量未知：${esc(error.message)}</p>`;
  }
}
document.addEventListener('click', e => {
  if (e.target.closest('[data-view="history"]')) { inventoryHistoryPage = 1; loadInventoryHistory(null); loadHistoricalReports(); }
  if (e.target.closest('[data-detail="runs"]') && state.selected) { cityHistoryPage = 1; loadInventoryHistory(state.selected); }
  if (e.target.closest('[data-detail="queries"]') && state.selected) { cityAuditPage = 1; loadCityAudit(state.selected); }
});
