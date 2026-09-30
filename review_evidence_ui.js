/* Development review evidence view: DOM textContent prevents evidence injection. */
(() => {
  let active = null;
  const modal = document.getElementById("evidenceModal");
  const root = document.getElementById("evidenceContent");
  const $ = (tag, value, parent) => {
    const el = document.createElement(tag);
    if (value !== undefined && value !== null) el.textContent = String(value);
    if (parent) parent.appendChild(el);
    return el;
  };
  const section = title => {
    const box = $("section", "", root);
    box.className = "evidence-section";
    $("h4", title, box);
    return box;
  };
  const field = (box, label, value) => {
    const row = $("div", "", box);
    row.className = "detail-row";
    $("strong", label + ": ", row);
    $("span", value === undefined || value === null || value === "" ? "-" : value, row);
  };
  const link = (box, label, value) => {
    const row = $("div", "", box);
    row.className = "detail-row";
    $("strong", label + ": ", row);
    try {
      const url = new URL(value);
      if (!["http:", "https:"].includes(url.protocol)) throw Error();
      const anchor = $("a", value, row);
      anchor.href = url.href;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
    } catch (_) { $("span", value || "-", row); }
  };
  const button = (box, label, callback, disabled) => {
    const el = $("button", label, box);
    el.className = "btn";
    el.disabled = Boolean(disabled);
    el.onclick = callback;
  };
  async function post(path, payload) {
    const response = await fetch(path, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    return response.json();
  }
  async function action(path) {
    const result = await post(path, {lead_id: active});
    if (!result.ok) alert(result.error || "失败 / Failed");
    await refresh();
  }
  async function judgment(value) {
    const reason = prompt("证据审核理由 / Evidence review reason");
    if (!reason) return;
    const result = await post("/api/evidence-decision", {lead_id: active, action: value, reason});
    alert(result.ok ? "已审计，发送资格不变 / Audited; eligibility unchanged" : result.error);
    await refresh();
  }
  async function refresh() {
    if (active === null) return;
    const data = await (await fetch("/api/review-evidence?lead_id=" + encodeURIComponent(active))).json();
    root.replaceChildren();
    if (!data.ok) { $("p", data.error || "Unavailable", root); return; }
    const l = data.lead_identity || {}, b = data.blocker_summary || {};
    const o = data.official_site_evidence || {}, f = data.facebook_evidence || {};
    const r = data.recovered_website || {};
    let box = section("1. 商家 / Merchant");
    field(box, "ID", l.id); field(box, "名称 / Name", l.store_name);
    field(box, "位置 / Location", [l.city,l.state].filter(Boolean).join(", "));
    field(box, "地址 / Address", l.formatted_address); field(box, "电话 / Phone", l.phone);
    box = section("2. 审核原因 / Why This Needs Review");
    field(box, "原因码 / Reason", b.reason_code); field(box, "说明 / Detail", b.detail);
    field(box, "优先级 / Priority", b.priority);
    field(box, "恢复价值 / Recovery Value", (b.recovery || {}).value);
    field(box, "历史阻断 / History Blockers", ((b.recovery || {}).reasons || []).join(", "));
    box = section("3. 当前邮箱 / Current Email");
    field(box, "邮箱 / Email", o.email); field(box, "来源 / Source", o.email_source_type);
    field(box, "官网已验证 / Official Verified", o.email_verified_on_official_site);
    box = section("4. 官网证据 / Official Site Evidence");
    link(box, "官网 / Website", o.official_website);
    link(box, "证据页 / Evidence URL", o.evidence_url);
    field(box, "字面片段 / Literal Excerpt", o.evidence_snippet);
    field(box, "方法 / Method", o.evidence_method);
    field(box, "核验时间 / Checked At", o.evidence_checked_at);
    field(box, "组织键 / Organization Key", o.organization_key);
    field(box, "时区 / Timezone", [o.timezone_status,o.recipient_timezone].filter(Boolean).join(" "));
    const t = data.website_enrichment_telemetry || {};
    const labels = {
      STATIC_FETCH_SUCCESS:"静态抓取成功 / Static fetch succeeded",
      STATIC_FETCH_FAILED:"静态抓取失败 / Static fetch failed",
      BROWSER_FALLBACK_ATTEMPTED:"已尝试浏览器 / Browser attempted",
      BROWSER_FALLBACK_SUCCESS:"浏览器成功 / Browser succeeded",
      BROWSER_FALLBACK_FAILED:"浏览器失败 / Browser failed",
      STRUCTURED_EMAIL_FOUND:"结构化邮箱已找到 / Structured email found",
      CONTACT_FORM_ONLY:"仅联系表单 / Contact form only",
      NO_EMAIL_ON_ACCEPTED_PAGE:"合格页面无邮箱 / No email on accepted pages",
      AUTOMATION_RECOVERY_EXHAUSTED:"恢复已穷尽 / Recovery exhausted"
    };
    field(box, "遥测 / Telemetry", Object.entries(labels).filter(([key])=>t[key]).map(([,v])=>v).join("; "));
    field(box, "结构化邮箱 / Structured Email", (data.structured_data_evidence || {}).present);
    box = section("5. Facebook 证据 / Facebook Evidence");
    field(box, "状态 / Status", f.status); link(box, "公开主页 / Public Page", f.facebook_page_url);
    field(box, "候选数 / Candidates Found", f.facebook_candidates_found);
    link(box, "选中候选 / Selected Candidate", f.facebook_candidate_selected);
    link(box, "官网发现来源 / Discovery Source", f.facebook_discovery_source_url);
    field(box, "其他候选仅供人工查看 / Other Candidates For Review",
      (f.facebook_other_candidates || []).join(", "));
    field(box, "来源等级 / Provenance Tier", f.facebook_provenance_tier);
    field(box, "邮箱来源 / Email Provenance", "官网直接关联 Facebook；仅人工证据 / Official-site-linked Facebook; manual evidence only");
    field(box, "正式资格来源 / Formal Eligibility Source", "尚未批准 / Not approved");
    field(box, "主页名称 / Page Name", f.facebook_page_name);
    field(box, "社交邮箱类别 / Email Class", f.social_email_class);
    field(box, "公开邮箱 / Public Email", f.public_email);
    field(box, "可见片段 / Visible Excerpt", f.visible_email_excerpt);
    field(box, "公开电话 / Public Phone", f.public_phone);
    field(box, "商业地址 / Business Address", f.public_business_address);
    field(box, "身份信号 / Identity Signals",
      Object.entries(f.identity_match_signals || {}).filter(([,v])=>v).map(([k])=>k).join(", "));
    field(box, "抓取时间 / Fetched At", f.fetched_at);
    field(box, "社交证据可直接成为 SAFE / SAFE From Social", f.safe_eligible_from_social === true ? "异常 / Unexpected" : "否 / No");
    box = section("6. 找回官网 / Recovered Website");
    link(box, "候选网站 / Candidate", f.public_website);
    field(box, "已验证 / Verified", r.verified);
    field(box, "第一方邮箱 / First-Party Email", (r.first_party_email_evidence || {}).email);
    field(box, "持久化 / Persisted", r.persisted);
    field(box, "原因 / Reason", r.reason);
    box = section("7. 安全与资格门禁 / Safety and Eligibility Gates");
    const grid = $("div", "", box);
    grid.className = "gate-grid";
    Object.entries(data.gate_matrix || {}).forEach(([key, value]) => {
      $("div", key + " — " + (typeof value.detail === "object" ? JSON.stringify(value.detail) : (value.detail || "")), grid);
      const verdict = $("div", value.state, grid);
      verdict.className = value.state === "PASS" ? "g" : (value.state === "UNKNOWN" ? "y" : "r");
    });
    field(box, "V1（当前已存邮箱） / V1 (stored email)", (data.v1_state || {}).pool);
    field(box, "V2（当前已存邮箱） / V2 (stored email)", (data.v2_state || {}).pool);
    field(box, "MX", (data.mx_state || {}).status);
    box = section("8. 审核操作 / Review Actions");
    const blocked = (b.recovery || {}).value === "NONE";
    button(box, "获取 Facebook 证据 / Fetch Facebook Evidence",
      ()=>action("/api/fetch-facebook-evidence"), blocked || data.browser_job_status === "running");
    button(box, "验证找回官网 / Verify Recovered Website",
      ()=>action("/api/verify-recovered-website"), !f.public_website || data.browser_job_status === "running");
    button(box, "接受身份依据 / Accept Identity Evidence",
      ()=>judgment("accept_facebook_identity"), f.status !== "opened");
    button(box, "拒绝匹配 / Reject Match",
      ()=>judgment("reject_facebook_match"), f.status !== "opened");
    button(box, "提交官方邮箱 / Submit Official Email", ()=>openEmailModal(l.id));
    field(box, "说明 / Note", "接受证据不授权发送 / Evidence acceptance never authorizes sending");
    box = section("9. 审计历史 / Audit History");
    (data.audit_history || []).forEach(item =>
      field(box, (item.reviewed_at || "") + " " + (item.decision || ""),
        (item.reviewer || "") + " — " + (item.reason_detail || "")));
    if (data.browser_job_status === "running")
      setTimeout(()=>{if (active === l.id) refresh();}, 1500);
  }
  window.openEvidence = async leadId => {
    active = Number(leadId);
    modal.classList.add("show");
    try { await refresh(); } catch (error) { root.textContent = String(error); }
  };
  window.closeEvidence = () => {
    active = null;
    modal.classList.remove("show");
  };
})();
