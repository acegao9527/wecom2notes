const state = {
  view: "overview",
  token: localStorage.getItem("wecom2notes.adminToken") || "",
  session: { auth_required: false },
  overview: null,
  targetTypes: [],
  destinations: [],
  routes: [],
  deliveries: [],
  messages: { items: [], total: 0, limit: 100, offset: 0 },
  selectedMessage: null,
  bindings: [],
};

const viewMeta = {
  overview: ["总览", "企业微信消息归档、投递目标和失败重试"],
  targets: ["目标", "配置和验证所有笔记投递目标"],
  routes: ["路由", "按消息条件把内容投递到不同目标"],
  deliveries: ["投递", "查看投递状态并重放失败消息"],
  messages: ["消息", "审计统一消息、附件和原始数据"],
  bindings: ["Craft 绑定", "管理兼容旧版的 Craft 用户绑定"],
};

const targetDefaults = {
  craft: { link_id: "", document_id: "", token: "" },
  markdown: { root_path: "/notes", base_dir: "WeCom", mode: "daily", asset_dir: "WeCom/assets" },
  obsidian: { root_path: "/notes", base_dir: "WeCom", mode: "daily", link_style: "wiki" },
  logseq: { root_path: "/notes", base_dir: "WeCom", mode: "daily" },
  notion: { token: "", page_id: "", database_id: "", title_property: "Name" },
  webdav: { base_url: "", root_path: "WeCom", username: "", password: "" },
  git: { root_path: "/notes", repo_path: "/notes", base_dir: "WeCom", mode: "daily", auto_commit: false },
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compact(value, length = 90) {
  const text = String(value ?? "");
  return text.length > length ? `${text.slice(0, length - 1)}...` : text;
}

function boolText(value) {
  return value ? "启用" : "停用";
}

function statusBadge(status) {
  if (status === "delivered" || status === true || status === "ok") {
    return `<span class="badge ok">正常</span>`;
  }
  if (status === "failed" || status === false) {
    return `<span class="badge fail">失败</span>`;
  }
  if (status === "pending") {
    return `<span class="badge warn">待处理</span>`;
  }
  return `<span class="badge info">${escapeHtml(status ?? "未知")}</span>`;
}

function enabledBadge(value) {
  return `<span class="badge ${value ? "ok" : "warn"}">${boolText(value)}</span>`;
}

function showNotice(message, error = false) {
  const el = $("#notice");
  el.textContent = message;
  el.classList.toggle("error", error);
  el.classList.remove("hidden");
  window.setTimeout(() => el.classList.add("hidden"), 4200);
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (state.token) {
    headers.set("X-Admin-Token", state.token);
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    $("#authPanel").classList.remove("hidden");
    throw new Error("需要 ADMIN_TOKEN");
  }
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof data === "object" ? data.detail || JSON.stringify(data) : data;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return data;
}

async function loadSession() {
  state.session = await apiFetch("/admin/session");
  $("#authStatus").textContent = state.session.auth_required ? "已启用" : "未启用";
  $("#authPanel").classList.toggle("hidden", !state.session.auth_required || Boolean(state.token));
}

async function loadCommon() {
  const [overview, destinations, routes, bindings] = await Promise.all([
    apiFetch("/admin/overview"),
    apiFetch("/admin/destinations"),
    apiFetch("/admin/routes"),
    apiFetch("/bindings"),
  ]);
  state.overview = overview;
  state.targetTypes = overview.target_types || [];
  state.destinations = destinations.items || [];
  state.routes = routes.items || [];
  state.bindings = bindings || [];
}

async function loadDeliveries(status = "") {
  const query = status ? `?status=${encodeURIComponent(status)}&limit=100` : "?limit=100";
  const data = await apiFetch(`/admin/deliveries${query}`);
  state.deliveries = data.items || [];
}

async function loadMessages(params = {}) {
  const query = new URLSearchParams();
  Object.entries({ source: "wecom", limit: 100, ...params }).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  });
  state.messages = await apiFetch(`/admin/messages?${query.toString()}`);
}

async function refreshCurrentView() {
  try {
    $("#apiStatus").textContent = "loading";
    if (state.view === "deliveries") {
      await loadDeliveries($("#deliveryStatus")?.value || "");
    } else if (state.view === "messages") {
      await loadMessages(Object.fromEntries(new FormData($("#messageFilterForm") || document.createElement("form"))));
    } else {
      await loadCommon();
    }
    render();
    $("#apiStatus").textContent = "ok";
  } catch (error) {
    $("#apiStatus").textContent = "error";
    showNotice(error.message, true);
  }
}

function setView(view) {
  state.view = view;
  const [title, hint] = viewMeta[view];
  $("#pageTitle").textContent = title;
  $("#pageHint").textContent = hint;
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  refreshCurrentView();
}

function render() {
  const template = $(`#${state.view}Template`);
  const content = $("#content");
  content.replaceChildren(template.content.cloneNode(true));
  if (state.view === "overview") renderOverview(content);
  if (state.view === "targets") renderTargets(content);
  if (state.view === "routes") renderRoutes(content);
  if (state.view === "deliveries") renderDeliveries(content);
  if (state.view === "messages") renderMessages(content);
  if (state.view === "bindings") renderBindings(content);
}

function renderOverview(root) {
  const metrics = state.overview?.metrics || {};
  const cards = [
    ["消息总数", metrics.messages_total, "unified_messages"],
    ["投递成功", metrics.deliveries_delivered, "deliveries delivered"],
    ["失败投递", metrics.deliveries_failed, "failed deliveries"],
    ["目标数量", metrics.destinations_total, "destinations"],
    ["当前 seq", state.overview?.runtime?.wecom_seq ?? 0, "/app/data/.wecom_seq"],
  ];
  $('[data-slot="metrics"]', root).innerHTML = cards
    .map(([label, value, note]) => `<article class="metric"><span>${label}</span><strong>${value ?? 0}</strong><small>${note}</small></article>`)
    .join("");

  const runtime = state.overview?.runtime || {};
  $('[data-slot="runtime"]', root).innerHTML = [
    ["SDK 禁用", runtime.wecom_disable_sdk ? "是" : "否"],
    ["数据库", runtime.sqlite_db_path],
    ["附件目录", runtime.image_save_dir],
    ["管理鉴权", runtime.admin_auth_enabled ? "ADMIN_TOKEN" : "未启用"],
    ["支持目标", (state.overview?.target_types || []).join(", ")],
  ]
    .map(([key, value]) => `<div class="kv-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");

  $('[data-slot="failed"]', root).innerHTML = smallDeliveryTable(state.overview?.recent_failed_deliveries || []);
  $('[data-slot="recentMessages"]', root).innerHTML = smallMessageTable(state.overview?.recent_messages || []);
}

function smallDeliveryTable(items) {
  if (!items.length) return `<div class="empty">没有失败投递。</div>`;
  return `<table><tbody>${items
    .map(
      (item) => `<tr>
        <td><div class="row-title"><strong>${escapeHtml(item.msg_id)} -> ${escapeHtml(item.target_id)}</strong><span>${escapeHtml(compact(item.error || item.external_id || ""))}</span></div></td>
        <td>${statusBadge(item.status)}</td>
      </tr>`,
    )
    .join("")}</tbody></table>`;
}

function smallMessageTable(items) {
  if (!items.length) return `<div class="empty">暂无消息。</div>`;
  return `<table><tbody>${items
    .map(
      (item) => `<tr>
        <td><div class="row-title"><strong>${escapeHtml(item.from_user || item.sender_name || "-")}</strong><span>${escapeHtml(compact(item.content || item.msg_id))}</span></div></td>
        <td><span class="badge info">${escapeHtml(item.msg_type)}</span></td>
      </tr>`,
    )
    .join("")}</tbody></table>`;
}

function renderTargets(root) {
  $('[data-slot="targetsTable"]', root).innerHTML = targetTable();
  fillTargetTypeSelect($("#targetForm select[name='target_type']", root));
}

function targetTable() {
  if (!state.destinations.length) return `<div class="empty">还没有目标，点击新增目标开始配置。</div>`;
  return `<table>
    <thead><tr><th>目标</th><th>类型</th><th>配置摘要</th><th>状态</th><th></th></tr></thead>
    <tbody>${state.destinations
      .map(
        (item) => `<tr>
          <td><div class="row-title"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.id)}</span></div></td>
          <td><span class="badge info">${escapeHtml(item.target_type)}</span></td>
          <td><code>${escapeHtml(compact(JSON.stringify(maskConfig(item.config)), 100))}</code></td>
          <td>${enabledBadge(item.is_enabled)}</td>
          <td class="actions">
            <button class="tiny" data-action="verify-target" data-id="${escapeHtml(item.id)}" title="验证">V</button>
            <button class="tiny" data-action="edit-target" data-id="${escapeHtml(item.id)}" title="编辑">E</button>
            <button class="tiny" data-action="toggle-target" data-id="${escapeHtml(item.id)}" title="启停">P</button>
            <button class="tiny" data-action="delete-target" data-id="${escapeHtml(item.id)}" title="删除">D</button>
          </td>
        </tr>`,
      )
      .join("")}</tbody></table>`;
}

function maskConfig(config = {}) {
  const masked = { ...config };
  for (const key of Object.keys(masked)) {
    if (/token|password|secret/i.test(key) && masked[key]) masked[key] = "***";
  }
  return masked;
}

function fillTargetTypeSelect(select) {
  if (!select) return;
  select.innerHTML = state.targetTypes.map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`).join("");
}

function renderRoutes(root) {
  $('[data-slot="routesTable"]', root).innerHTML = routeTable();
  fillDestinationSelect($("#routeForm select[name='destination_id']", root));
}

function routeTable() {
  if (!state.routes.length) return `<div class="empty">还没有路由规则。</div>`;
  return `<table>
    <thead><tr><th>规则</th><th>匹配条件</th><th>目标</th><th>状态</th><th></th></tr></thead>
    <tbody>${state.routes
      .map(
        (item) => `<tr>
          <td><div class="row-title"><strong>${escapeHtml(item.name || `route-${item.id}`)}</strong><span>#${item.id}</span></div></td>
          <td>${routeChips(item)}</td>
          <td><span class="badge info">${escapeHtml(item.destination_id)}</span></td>
          <td>${enabledBadge(Boolean(item.is_enabled))}</td>
          <td class="actions">
            <button class="tiny" data-action="edit-route" data-id="${item.id}" title="编辑">E</button>
            <button class="tiny" data-action="toggle-route" data-id="${item.id}" title="启停">P</button>
            <button class="tiny" data-action="delete-route" data-id="${item.id}" title="删除">D</button>
          </td>
        </tr>`,
      )
      .join("")}</tbody></table>`;
}

function routeChips(route) {
  return ["source", "from_user", "chat_id", "msg_type", "keyword"]
    .filter((key) => route[key])
    .map((key) => `<span class="badge violet">${escapeHtml(key)}=${escapeHtml(route[key])}</span>`)
    .join(" ") || `<span class="muted">全部消息</span>`;
}

function fillDestinationSelect(select) {
  if (!select) return;
  select.innerHTML = state.destinations
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} (${escapeHtml(item.id)})</option>`)
    .join("");
}

function renderDeliveries(root) {
  $('[data-slot="deliveriesTable"]', root).innerHTML = deliveryTable();
  const status = $("#deliveryStatus", root);
  if (status) status.addEventListener("change", () => loadDeliveries(status.value).then(() => render()).catch((error) => showNotice(error.message, true)));
}

function deliveryTable() {
  if (!state.deliveries.length) return `<div class="empty">当前筛选下没有投递记录。</div>`;
  return `<table>
    <thead><tr><th>消息</th><th>目标</th><th>状态</th><th>尝试</th><th>错误/外部 ID</th><th></th></tr></thead>
    <tbody>${state.deliveries
      .map(
        (item) => `<tr>
          <td><div class="row-title"><strong>${escapeHtml(item.msg_id)}</strong><span>${escapeHtml(item.source)}</span></div></td>
          <td>${escapeHtml(item.target_id)}<br><span class="muted">${escapeHtml(item.target_type)}</span></td>
          <td>${statusBadge(item.status)}</td>
          <td>${item.attempts ?? 0}</td>
          <td>${escapeHtml(compact(item.error || item.external_id || ""))}</td>
          <td class="actions"><button class="tiny" data-action="replay-message" data-source="${escapeHtml(item.source)}" data-msg-id="${escapeHtml(item.msg_id)}" title="重放">R</button></td>
        </tr>`,
      )
      .join("")}</tbody></table>`;
}

function renderMessages(root) {
  $('[data-slot="messagesTable"]', root).innerHTML = messageTable();
  renderMessageDetail($('[data-slot="messageDetail"]', root));
}

function messageTable() {
  if (!state.messages.items.length) return `<div class="empty">没有匹配消息。</div>`;
  return `<table>
    <thead><tr><th>时间</th><th>发送人</th><th>类型</th><th>内容</th><th>投递</th></tr></thead>
    <tbody>${state.messages.items
      .map(
        (item) => `<tr data-action="select-message" data-source="${escapeHtml(item.source)}" data-msg-id="${escapeHtml(item.msg_id)}">
          <td>${escapeHtml(item.created_at || "")}</td>
          <td><div class="row-title"><strong>${escapeHtml(item.sender_name || item.from_user || "-")}</strong><span>${escapeHtml(item.chat_id || "")}</span></div></td>
          <td><span class="badge info">${escapeHtml(item.msg_type)}</span></td>
          <td>${escapeHtml(compact(item.content || item.msg_id, 80))}</td>
          <td><span class="badge ${item.deliveries_failed ? "fail" : "ok"}">${item.deliveries_delivered || 0}/${item.deliveries_total || 0}</span></td>
        </tr>`,
      )
      .join("")}</tbody></table>`;
}

function renderMessageDetail(container) {
  if (!container) return;
  if (!state.selectedMessage) {
    container.innerHTML = `<div class="empty">选择一条消息查看详情。</div>`;
    return;
  }
  const { message, attachments = [], deliveries = [] } = state.selectedMessage;
  container.innerHTML = `
    <div class="detail-card">
      <h3>${escapeHtml(message.msg_id)}</h3>
      <div class="kv-list">
        ${[
          ["source", message.source],
          ["from_user", message.from_user],
          ["chat_id", message.chat_id || "-"],
          ["created_at", message.created_at || "-"],
        ]
          .map(([key, value]) => `<div class="kv-row"><span>${key}</span><strong>${escapeHtml(value)}</strong></div>`)
          .join("")}
      </div>
      <button class="button" data-action="replay-message" data-source="${escapeHtml(message.source)}" data-msg-id="${escapeHtml(message.msg_id)}" type="button">重放消息</button>
    </div>
    <div class="detail-card">
      <h3>附件</h3>
      ${attachments.length ? attachments.map((item) => `<p>${escapeHtml(item.file_name || item.local_path || item.url)}</p>`).join("") : `<p class="muted">无附件</p>`}
    </div>
    <div class="detail-card">
      <h3>投递</h3>
      ${deliveries.length ? deliveries.map((item) => `<p>${statusBadge(item.status)} ${escapeHtml(item.target_id)} ${escapeHtml(item.error || "")}</p>`).join("") : `<p class="muted">无投递记录</p>`}
    </div>
    <pre class="json-box">${escapeHtml(JSON.stringify(message.raw_data || {}, null, 2))}</pre>
  `;
}

function renderBindings(root) {
  $('[data-slot="bindingsTable"]', root).innerHTML = bindingTable();
}

function bindingTable() {
  if (!state.bindings.length) return `<div class="empty">还没有 Craft 绑定。</div>`;
  return `<table>
    <thead><tr><th>用户</th><th>Craft</th><th>状态</th><th>创建时间</th><th></th></tr></thead>
    <tbody>${state.bindings
      .map(
        (item) => `<tr>
          <td><div class="row-title"><strong>${escapeHtml(item.display_name || item.wecom_openid)}</strong><span>${escapeHtml(item.wecom_openid)}</span></div></td>
          <td>${escapeHtml(item.craft_link_id)}<br><span class="muted">${escapeHtml(item.craft_document_id)}</span></td>
          <td>${enabledBadge(item.is_enabled)}</td>
          <td>${escapeHtml(item.created_at || "")}</td>
          <td class="actions">
            <button class="tiny" data-action="edit-binding" data-openid="${escapeHtml(item.wecom_openid)}" title="编辑">E</button>
            <button class="tiny" data-action="toggle-binding" data-openid="${escapeHtml(item.wecom_openid)}" title="启停">P</button>
            <button class="tiny" data-action="delete-binding" data-openid="${escapeHtml(item.wecom_openid)}" title="删除">D</button>
          </td>
        </tr>`,
      )
      .join("")}</tbody></table>`;
}

function showTargetForm(item = null) {
  const panel = $('[data-slot="targetFormPanel"]');
  const form = $("#targetForm");
  panel.classList.remove("hidden");
  $('[data-slot="targetFormTitle"]').textContent = item ? "编辑目标" : "新增目标";
  fillTargetTypeSelect(form.elements.target_type);
  form.elements.original_id.value = item?.id || "";
  form.elements.id.value = item?.id || "";
  form.elements.id.disabled = Boolean(item);
  form.elements.name.value = item?.name || "";
  form.elements.target_type.value = item?.target_type || state.targetTypes[0] || "markdown";
  form.elements.is_enabled.value = String(item?.is_enabled ?? true);
  form.elements.config.value = JSON.stringify(item?.config || targetDefaults[form.elements.target_type.value] || {}, null, 2);
}

function showRouteForm(item = null) {
  const panel = $('[data-slot="routeFormPanel"]');
  const form = $("#routeForm");
  panel.classList.remove("hidden");
  $('[data-slot="routeFormTitle"]').textContent = item ? "编辑规则" : "新增规则";
  fillDestinationSelect(form.elements.destination_id);
  for (const key of ["id", "name", "source", "from_user", "chat_id", "msg_type", "keyword", "destination_id", "template"]) {
    if (form.elements[key]) form.elements[key].value = item?.[key] || (key === "source" ? "wecom" : "");
  }
  form.elements.is_enabled.value = String(Boolean(item?.is_enabled ?? true));
}

async function handleTargetSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  let config;
  try {
    config = JSON.parse(form.elements.config.value || "{}");
  } catch {
    showNotice("配置 JSON 格式不正确", true);
    return;
  }
  const originalId = form.elements.original_id.value;
  const payload = {
    id: originalId || form.elements.id.value.trim(),
    name: form.elements.name.value.trim(),
    target_type: form.elements.target_type.value,
    config,
    is_enabled: form.elements.is_enabled.value === "true",
  };
  const path = originalId ? `/admin/destinations/${encodeURIComponent(originalId)}` : "/admin/destinations";
  await apiFetch(path, { method: originalId ? "PUT" : "POST", body: JSON.stringify(payload) });
  showNotice("目标已保存");
  await refreshCurrentView();
}

async function handleRouteSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const id = form.elements.id.value;
  const payload = Object.fromEntries(new FormData(form));
  payload.is_enabled = form.elements.is_enabled.value === "true";
  delete payload.id;
  const path = id ? `/admin/routes/${encodeURIComponent(id)}` : "/admin/routes";
  await apiFetch(path, { method: id ? "PUT" : "POST", body: JSON.stringify(payload) });
  showNotice("路由已保存");
  await refreshCurrentView();
}

async function handleRouteTest(event) {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget));
  payload.source = "wecom";
  const data = await apiFetch("/admin/routes/test", { method: "POST", body: JSON.stringify(payload) });
  $('[data-slot="routeTestResult"]').innerHTML = data.items.length
    ? data.items.map((item) => `<span class="badge info">${escapeHtml(item.id)} (${escapeHtml(item.target_type)})</span>`).join(" ")
    : "没有命中目标";
}

async function handleMessageFilter(event) {
  event.preventDefault();
  await loadMessages(Object.fromEntries(new FormData(event.currentTarget)));
  state.selectedMessage = null;
  render();
}

async function handleBindingSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const editing = form.elements.editing_openid.value;
  const payload = Object.fromEntries(new FormData(form));
  payload.is_enabled = form.elements.is_enabled.value === "true";
  delete payload.editing_openid;
  const path = editing ? `/bindings/${encodeURIComponent(editing)}` : "/bindings";
  await apiFetch(path, { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
  showNotice("绑定已保存");
  await loadCommon();
  render();
}

async function handleAction(action, button) {
  if (action === "new-target") return showTargetForm();
  if (action === "new-route") return showRouteForm();
  if (action === "cancel-form") return button.closest(".form-panel")?.classList.add("hidden");
  if (action === "edit-target") return showTargetForm(state.destinations.find((item) => item.id === button.dataset.id));
  if (action === "edit-route") return showRouteForm(state.routes.find((item) => String(item.id) === button.dataset.id));
  if (action === "verify-target") {
    const data = await apiFetch(`/admin/destinations/${encodeURIComponent(button.dataset.id)}/verify`, { method: "POST" });
    return showNotice(data.result?.error || data.result?.status || "验证完成", data.status !== "success");
  }
  if (action === "toggle-target") {
    const item = state.destinations.find((dest) => dest.id === button.dataset.id);
    await apiFetch(`/admin/destinations/${encodeURIComponent(item.id)}/enabled`, { method: "PATCH", body: JSON.stringify({ is_enabled: !item.is_enabled }) });
    return refreshCurrentView();
  }
  if (action === "delete-target") {
    if (!window.confirm("删除目标会同时删除关联路由，确认继续？")) return;
    await apiFetch(`/admin/destinations/${encodeURIComponent(button.dataset.id)}`, { method: "DELETE" });
    return refreshCurrentView();
  }
  if (action === "toggle-route") {
    const item = state.routes.find((route) => String(route.id) === button.dataset.id);
    await apiFetch(`/admin/routes/${encodeURIComponent(item.id)}/enabled`, { method: "PATCH", body: JSON.stringify({ is_enabled: !item.is_enabled }) });
    return refreshCurrentView();
  }
  if (action === "delete-route") {
    if (!window.confirm("确认删除这条路由？")) return;
    await apiFetch(`/admin/routes/${encodeURIComponent(button.dataset.id)}`, { method: "DELETE" });
    return refreshCurrentView();
  }
  if (action === "select-message") {
    state.selectedMessage = await apiFetch(`/admin/messages/${encodeURIComponent(button.dataset.source)}/${encodeURIComponent(button.dataset.msgId)}`);
    return render();
  }
  if (action === "replay-message") {
    await apiFetch("/admin/replay", {
      method: "POST",
      body: JSON.stringify({ source: button.dataset.source, msg_id: button.dataset.msgId, force: true }),
    });
    showNotice("消息已重放");
    return refreshCurrentView();
  }
  if (action === "edit-binding") {
    const item = state.bindings.find((binding) => binding.wecom_openid === button.dataset.openid);
    const form = $("#bindingForm");
    form.elements.editing_openid.value = item.wecom_openid;
    form.elements.wecom_openid.value = item.wecom_openid;
    form.elements.display_name.value = item.display_name || "";
    form.elements.craft_link_id.value = item.craft_link_id;
    form.elements.craft_document_id.value = item.craft_document_id;
    form.elements.craft_token.value = "";
    form.elements.is_enabled.value = String(item.is_enabled);
    return;
  }
  if (action === "toggle-binding") {
    const item = state.bindings.find((binding) => binding.wecom_openid === button.dataset.openid);
    await apiFetch(`/bindings/${encodeURIComponent(item.wecom_openid)}/enabled`, { method: "PATCH", body: JSON.stringify({ is_enabled: !item.is_enabled }) });
    return refreshCurrentView();
  }
  if (action === "delete-binding") {
    if (!window.confirm("确认删除这个 Craft 绑定？")) return;
    await apiFetch(`/bindings/${encodeURIComponent(button.dataset.openid)}`, { method: "DELETE" });
    return refreshCurrentView();
  }
  if (action === "verify-binding-form") {
    const form = $("#bindingForm");
    const payload = {
      link_id: form.elements.craft_link_id.value,
      document_id: form.elements.craft_document_id.value,
      token: form.elements.craft_token.value,
    };
    const data = await apiFetch("/bindings/verify", { method: "POST", body: JSON.stringify(payload) });
    return showNotice(data.message || "验证成功");
  }
}

function bindEvents() {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    try {
      await handleAction(button.dataset.action, button);
    } catch (error) {
      showNotice(error.message, true);
    }
  });
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));
  $("#refreshButton").addEventListener("click", refreshCurrentView);
  $("#logoutButton").addEventListener("click", () => {
    localStorage.removeItem("wecom2notes.adminToken");
    state.token = "";
    $("#authPanel").classList.remove("hidden");
  });
  $("#authForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    state.token = new FormData(event.currentTarget).get("token");
    localStorage.setItem("wecom2notes.adminToken", state.token);
    $("#authPanel").classList.add("hidden");
    await refreshCurrentView();
  });
  $("#content").addEventListener("submit", async (event) => {
    try {
      if (event.target.id === "targetForm") return await handleTargetSubmit(event);
      if (event.target.id === "routeForm") return await handleRouteSubmit(event);
      if (event.target.id === "routeTestForm") return await handleRouteTest(event);
      if (event.target.id === "messageFilterForm") return await handleMessageFilter(event);
      if (event.target.id === "bindingForm") return await handleBindingSubmit(event);
    } catch (error) {
      event.preventDefault();
      showNotice(error.message, true);
    }
  });
  $("#content").addEventListener("change", (event) => {
    if (event.target.matches("#targetForm select[name='target_type']")) {
      const textarea = $("#targetForm textarea[name='config']");
      textarea.value = JSON.stringify(targetDefaults[event.target.value] || {}, null, 2);
    }
  });
  $("#globalSearch").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      state.view = "messages";
      const [title, hint] = viewMeta.messages;
      $("#pageTitle").textContent = title;
      $("#pageHint").textContent = hint;
      $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === "messages"));
      loadMessages({ keyword: event.currentTarget.value, source: "wecom" }).then(render).catch((error) => showNotice(error.message, true));
    }
  });
}

async function boot() {
  bindEvents();
  try {
    await loadSession();
    await loadCommon();
    render();
    $("#apiStatus").textContent = "ok";
  } catch (error) {
    $("#apiStatus").textContent = "error";
    showNotice(error.message, true);
  }
}

boot();
