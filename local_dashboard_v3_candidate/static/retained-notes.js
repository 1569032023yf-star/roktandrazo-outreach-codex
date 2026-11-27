'use strict';
let notesRequest = 0;
let notesDirty = false;
const notesPanel = $('retained-notes-panel');
const savedPanel = document.createElement('section');
savedPanel.className = 'panel';
notesPanel.before(savedPanel);

async function loadSavedRetained(city) {
  try {
    const result = await api(`/api/retained-saved?city=${encodeURIComponent(city)}`);
    if (city !== state.selected) return;
    const term = state.rsearch.trim().toLocaleLowerCase(), reason = state.reason;
    const shown = result.items.filter(m => {
      const local = m.local_annotation || {};
      const match = !term || String(m.business_name || '').toLocaleLowerCase().includes(term) || String(m.id) === term.replace(/^ldr:/, '');
      const missing = !reason || (reason === 'email' && !String(local.email || m.email || '').trim()) ||
        (reason === 'website' && !String(local.website || m.website || '').trim()) ||
        (reason === 'identity' && !local.verified && (['identity_review','review_recovery','manual_review_needed'].includes(m.validation_status) || m.official_match !== 1));
      return match && missing;
    });
    const cards = shown.map(m => {
      const local = m.local_annotation;
      const supplement = local ? `<div class="panel"><strong>本机人工补充 · 版本 ${esc(local.revision)}</strong><div>官网：${link(local.website)}<br>邮箱（未验证）：${esc(local.email || '未填')}<br>联系方式：${esc(local.contact || '未填')}<br>备注：${esc(local.note || '未填')}<br>资料依据：${esc(local.evidence || '未填')}<br>人工标记：${local.verified ? '已核实' : '待核实'} · ${esc(local.created_at)}</div></div>` : '';
      return merchantCards([m], true) + supplement;
    }).join('') || '<div class="empty">当前筛选没有记录。</div>';
    savedPanel.innerHTML = `<h3>本机保留资料（${result.total}，当前筛选 ${shown.length}）</h3><p class="hint">来源资料与本机人工补充分开显示；筛选同时考虑两者。本机核实标记不代表正式资格。</p><button class="secondary" data-retained-capture>收存本城市待核查资料到本机</button><p class="hint" id="capture-message" role="status">只复制现有待核查及资料待补记录；不会修改生产资料、关闭城市、启动搜索或授予发信资格。</p>${cards}`;
  } catch (error) {
    if (city === state.selected) savedPanel.innerHTML = `<div class="error">本机已保存线索读取失败：${esc(error.message)}</div>`;
  }
}

document.addEventListener('click', async event => {
  const capture = event.target.closest('[data-retained-capture]');
  if (capture) {
    const city = state.selected;
    capture.disabled = true;
    $('capture-message').textContent = '正在只读取现有记录并收存到本机…';
    try {
      const result = await post('/api/retained-capture', {city_id: city});
      if (city !== state.selected) return;
      await loadSavedRetained(city);
      $('capture-message').textContent = `本次来源 ${result.source_matched} 条，新增原始快照 ${result.new_snapshots} 条，新增来源版本 ${result.new_observations ?? '服务尚未更新'} 条；原有快照均保留，没有修改生产。`;
    } catch (error) {
      if (city === state.selected) $('capture-message').textContent = '收存未完成：' + error.message;
    } finally { capture.disabled = false; }
    return;
  }
  const button = event.target.closest('[data-retained-edit]');
  if (!button) return;
  if (notesDirty && !confirm('打开其他线索会放弃当前未保存的补充内容，继续吗？')) return;
  const city = state.selected, id = Number(button.dataset.retainedEdit), request = ++notesRequest;
  const name = button.closest('.merchant')?.querySelector('strong')?.textContent || '商家';
  button.disabled = true;
  try {
    const data = await api(`/api/retained-notes?city=${encodeURIComponent(city)}&id=${encodeURIComponent(id)}`);
    if (request !== notesRequest || city !== state.selected) return;
    const current = data.versions[0] || {}, revision = current.revision || 0, observations = data.observations || [];
    notesPanel.innerHTML = `<div class="panel"><h3>本机补充：${esc(name)} · ldr:${id}</h3>
      <p class="warning">仅保存到本机独立资料库；不会修改正式商家信息，也不会进入发送名单。请自行备份本机资料库。</p>
      <form id="notes-form" class="plan-form"><label>补充官网 <input id="notes-website" maxlength="2000"></label>
      <label>补充邮箱（未验证） <input id="notes-email" maxlength="254"></label>
      <label>其他公开联系方式 <input id="notes-contact" maxlength="1000"></label>
      <label>人工备注 <textarea id="notes-note" maxlength="4000"></textarea></label>
      <label>资料来源或核实依据 <textarea id="notes-evidence" maxlength="2000"></textarea></label>
      <label><input type="checkbox" id="notes-verified"> 本机人工标记已核实（不代表发送资格）</label>
      <div><button class="primary">保存本机补充</button> <button type="button" id="notes-close" class="secondary">关闭</button></div>
      <div id="notes-message" role="status"></div></form>
      <details><summary>来源收存历史（${observations.length}）</summary>${observations.map(v =>
        `<div class="timeline-item"><strong>来源版本 ${v.revision} · ${esc(v.observed_at)}</strong><div>名称：${esc(v.source.business_name || '未知')}<br>地址：${esc(v.source.formatted_address || '未知')}<br>官网候选：${esc(v.source.website || '未知')}<br>邮箱：${esc(v.source.email || '未知')}<br>来源：${esc(v.source.source_url || '未知')}<br>状态：${esc(v.source.validation_status || '未知')}</div></div>`).join('') || '暂无来源版本；旧快照会在下次收存时保留并记录。'}</details>
      <details><summary>人工补充历史（${data.versions.length}）</summary>${data.versions.map(v =>
        `<div class="timeline-item"><strong>版本 ${v.revision} · ${esc(v.created_at)}</strong><div>官网：${esc(v.website || '未填')}<br>邮箱：${esc(v.email || '未填')}<br>联系方式：${esc(v.contact || '未填')}<br>备注：${esc(v.note || '未填')}<br>来源：${esc(v.evidence || '未填')}<br>本机标记：${v.verified ? '已核实' : '待核实'}</div></div>`).join('') || '暂无记录'}</details></div>`;
    for (const key of ['website', 'email', 'contact', 'note', 'evidence']) $('notes-' + key).value = current[key] || '';
    $('notes-verified').checked = Boolean(current.verified);
    notesPanel.hidden = false;
    notesDirty = false;
    $('notes-form').oninput = () => { notesDirty = true; };
    $('notes-close').onclick = () => {
      if (notesDirty && !confirm('关闭会放弃当前未保存的补充内容，继续吗？')) return;
      notesPanel.hidden = true; notesDirty = false;
    };
    $('notes-form').onsubmit = async e => {
      e.preventDefault();
      if (city !== state.selected) { $('notes-message').textContent = '城市已切换，不能保存；请回到原城市重新打开线索。'; return; }
      const submit = e.submitter;
      submit.disabled = true;
      const form = e.currentTarget;
      for (const field of form.querySelectorAll('input,textarea,button')) field.disabled = true;
      try {
        const result = await post('/api/retained-notes', {city_id:city, discovery_id:id, revision,
          website:$('notes-website').value, email:$('notes-email').value, contact:$('notes-contact').value,
          note:$('notes-note').value, evidence:$('notes-evidence').value, verified:$('notes-verified').checked});
        notesDirty = false;
        $('notes-message').textContent = `已保存本机版本 ${result.revision}；再次编辑请重新打开线索。`;
        loadSavedRetained(city);
        $('notes-close').disabled = false;
      } catch (error) {
        $('notes-message').textContent = '保存失败：' + error.message;
        for (const field of form.querySelectorAll('input,textarea,button')) field.disabled = false;
      }
    };
    notesPanel.scrollIntoView({behavior:'smooth'});
  } catch (error) { notice('读取本机补充失败：' + error.message, true); }
  finally { button.disabled = false; }
});
