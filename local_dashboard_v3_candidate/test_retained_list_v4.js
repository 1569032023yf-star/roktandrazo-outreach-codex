'use strict';
// Exercise the actual list rendering with synthetic records only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const saved = {innerHTML: '', className: ''};
const state = {selected: 5, rsearch: '', reason: ''};
const context = {
  state,
  $: () => ({before() {}}),
  document: {createElement() { return saved; }, addEventListener() {}},
  api: async () => ({total: 3, items: [
    {id: 1, business_name: 'Manual', validation_status: 'manual_review_needed', official_match: 0,
      email: '', website: '', local_annotation: {revision: 1, email: 'manual@example.test',
        website: 'https://manual.example.test', verified: 1, created_at: '2026-01-01'}},
    {id: 2, business_name: 'Missing', validation_status: 'manual_review_needed', official_match: 0,
      email: '', website: '', local_annotation: null},
    {id: 3, business_name: 'Source', validation_status: 'review_recovery', official_match: 0,
      email: 'source@example.test', website: 'https://source.example.test', local_annotation: null},
  ]}),
  merchantCards: items => items.map(m => `<article>${m.business_name}</article>`).join(''),
  esc: value => String(value ?? ''),
  link: value => value || '未记录',
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, 'static', 'retained-notes.js'), 'utf8'), context);

(async () => {
  await context.loadSavedRetained(5);
  assert.match(saved.innerHTML, /本机人工补充/);
  assert.match(saved.innerHTML, /manual@example\.test/);
  for (const reason of ['email', 'website', 'identity']) {
    state.reason = reason;
    await context.loadSavedRetained(5);
    assert.match(saved.innerHTML, /Missing/);
    assert.doesNotMatch(saved.innerHTML, /<article>Manual<\/article>/);
    if (reason !== 'identity') assert.doesNotMatch(saved.innerHTML, /<article>Source<\/article>/);
  }
  state.reason = '';
  state.rsearch = 'manual';
  await context.loadSavedRetained(5);
  assert.match(saved.innerHTML, /<article>Manual<\/article>/);
  assert.doesNotMatch(saved.innerHTML, /<article>Missing<\/article>/);
  console.log('Synthetic retained-lead display and filtering passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
