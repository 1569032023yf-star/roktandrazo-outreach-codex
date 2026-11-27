'use strict';
let templateData = null;
let templateRevision = 0;
let templateLoaded = false;
let templateLoading = false;
let templateSaving = false;
let templateUploading = false;
let previewSequence = 0;
let templateTarget = 'template-html';
const assetCache = new Map();
const examples = {merchant_name: 'Example Toy Store', contact_name: 'Alex', product_name: 'ROKT & RAZO'};
const sample = s => s.replace(/\{\{\s*(merchant_name|contact_name|product_name)\s*\}\}/g, (_, key) => examples[key]);
function templateControls() {
  const locked = !templateLoaded || templateLoading || templateSaving || templateUploading;
  for (const id of ['template-save', 'template-versions', 'template-upload', 'template-subject', 'template-html', 'template-text']) $(id).disabled = locked;
  document.querySelectorAll('[data-template-var]').forEach(control => { control.disabled = locked; });
  $('template-reload').disabled = templateLoading || templateSaving || templateUploading;
}
function templateMessage(message, error=false) {
  $('template-message').textContent = message;
  $('template-message').className = error ? 'error' : 'success';
}
function templateFill(v) {
  $('template-subject').value = v?.subject || '';
  $('template-html').value = v?.html || '';
  $('template-text').value = v?.text || '';
  templatePreview();
}
async function templateLoad() {
  if (templateLoading) return false;
  templateLoading = true;
  templateControls();
  try {
    const data = await api('/api/templates');
    templateData = data;
    templateRevision = data.versions[0]?.version || 0;
    $('template-versions').innerHTML = data.versions.length
      ? data.versions.map(v => `<option value="${v.version}">版本 ${v.version} · ${esc(v.created_at)}</option>`).join('')
      : '<option value="">暂无保存版本</option>';
    templateFill(data.versions[0]);
    templateLoaded = true;
    templateMessage(templateRevision ? `已读取本机版本 ${templateRevision}；未发布到正式发送。` : '尚无保存的模板，填写后可保存本机草稿。');
    return true;
  } catch (e) { templateMessage('读取模板失败：' + e.message, true); return false; }
  finally { templateLoading = false; templateControls(); }
}
function insertAt(field, text) {
  const input = $(field), start = input.selectionStart ?? input.value.length, end = input.selectionEnd ?? start;
  input.setRangeText(text, start, end, 'end');
  input.focus();
  templatePreview();
}
async function assetData(id) {
  if (!assetCache.has(id)) {
    const result = await api('/api/template-asset?id=' + encodeURIComponent(id));
    assetCache.set(id, `data:${result.mime};base64,${result.data}`);
  }
  return assetCache.get(id);
}
async function templatePreview() {
  const sequence = ++previewSequence;
  $('template-preview-subject').textContent = sample($('template-subject').value);
  $('template-preview-text').textContent = sample($('template-text').value);
  let html = sample($('template-html').value);
  const ids = [...new Set([...html.matchAll(/cid:([0-9a-f]{64})@rokt-local/gi)].map(x => x[1].toLowerCase()))];
  for (const id of ids) {
    try {
      const data = await assetData(id);
      html = html.replace(new RegExp('cid:' + id + '@rokt-local', 'gi'), data);
    } catch (_) { /* keep unresolved CID visible as a broken image */ }
  }
  if (sequence !== previewSequence) return;
  $('template-preview').srcdoc = '<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; form-action \'none\'">' + html;
}
document.addEventListener('click', e => {
  if (e.target.closest('[data-view="templates"]') && !templateLoaded) templateLoad();
  const variable = e.target.closest('[data-template-var]');
  if (variable) insertAt(templateTarget, '{{' + variable.dataset.templateVar + '}}');
  const size = e.target.closest('[data-preview-size]');
  if (size) $('template-preview').classList.toggle('mobile', size.dataset.previewSize === 'mobile');
});
for (const id of ['template-subject', 'template-html', 'template-text']) {
  $(id).addEventListener('focus', () => { templateTarget = id; });
  $(id).addEventListener('input', templatePreview);
}
$('template-reload').onclick = () => {
  if (confirm('重新读取会放弃当前未保存的编辑，继续吗？')) templateLoad();
};
$('template-versions').onchange = e => {
  if (!confirm('载入历史版本会替换当前编辑区内容，继续吗？')) {
    e.target.value = String(templateRevision); return;
  }
  templateFill(templateData.versions.find(v => v.version === Number(e.target.value)));
};
$('template-save').onclick = async () => {
  if (templateSaving || templateLoading || !templateLoaded) return;
  templateSaving = true;
  templateControls();
  try {
    const result = await post('/api/template-save', {revision:templateRevision,
      subject:$('template-subject').value, html:$('template-html').value, text:$('template-text').value});
    if (await templateLoad()) templateMessage(`已保存本机版本 ${result.version.version}；正式发信模板未改变。`);
    else {
      templateLoaded = false;
      templateMessage(`本机版本 ${result.version.version} 已保存，但读取最新版本失败；请重新读取后继续编辑。`, true);
    }
  } catch (e) { templateMessage('保存失败：' + e.message, true); }
  finally { templateSaving = false; templateControls(); }
};
$('template-upload').onchange = async e => {
  const file = e.target.files[0];
  if (!file) return;
  if (file.size > 2000000) { templateMessage('图片超过 2 MB。', true); e.target.value = ''; return; }
  templateUploading = true;
  templateControls();
  try {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('图片读取失败')); reader.readAsDataURL(file);
    });
    const image = await post('/api/template-asset', {data: dataUrl.split(',')[1]});
    insertAt('template-html', `<img src="${image.cid}" alt="产品图片">`);
    templateMessage('图片已保存到本机，并插入正文；请保存草稿版本。');
  } catch (err) { templateMessage('图片保存失败：' + err.message, true); }
  finally { e.target.value = ''; templateUploading = false; templateControls(); }
};
