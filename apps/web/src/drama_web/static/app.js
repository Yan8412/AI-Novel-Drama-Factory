const STAGES = [
  "created",
  "characters",
  "outline",
  "chapters",
  "novel_review",
  "storyboard",
  "storyboard_review",
  "assets",
  "image_review",
  "video",
  "video_review",
  "export",
  "done",
];

const STAGE_LABELS = {
  created: "已创建",
  characters: "人设",
  outline: "大纲",
  chapters: "章节",
  novel_review: "小说审核",
  storyboard: "分镜",
  storyboard_review: "分镜审核",
  assets: "资产",
  image_review: "图像审核",
  video: "视频",
  video_review: "视频审核",
  export: "导出",
  done: "完成",
  failed: "失败",
};

const LICENSE_LABELS = {
  unknown: "未标明",
  original: "原创占位",
  licensed: "已授权占位",
};

const state = {
  route: parseRoute(),
  genres: null,
  projects: [],
  project: null,
  exports: null,
  budget: null,
  reviews: null,
  usage: null,
  job: null,
  error: "",
  notice: "",
  busy: false,
  genrePick: "都市",
  reviewFilter: "pending",
  overrideReason: "人工覆盖",
};

function parseRoute() {
  const hash = (location.hash || "#/").replace(/^#/, "");
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "new") return { name: "create" };
  if (parts[0] === "p" && parts[1]) return { name: "detail", id: parts[1] };
  return { name: "list" };
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmtTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function stageChip(stage) {
  const kind = stage === "done" ? "ok" : stage === "failed" ? "fail" : "warn";
  return `<span class="chip ${kind}">${esc(STAGE_LABELS[stage] || stage)}</span>`;
}

function money(value, digits = 4) {
  const num = Number(value || 0);
  if (Number.isNaN(num)) return "0";
  return num.toFixed(digits);
}

function usageStrip() {
  const usage = state.usage;
  if (!usage) return "";
  const quota = usage.quota || {};
  const units = usage.units || {};
  const warn = quota.warning
    ? `<div class="banner ${quota.hard_exceeded ? "error" : "info"}">${esc(quota.warning)}</div>`
    : "";
  return `
    ${warn}
    <p class="muted">
      工作区账本 USD ${esc(money(usage.estimated_usd))}
      · CNY ${esc(money(usage.estimated_cny))}
      · token ${esc(units.tokens || 0)}
      · 图 ${esc(units.images || 0)}
      · 视频 ${esc(units.video_seconds || 0)}s
      · TTS ${esc(units.tts_chars || 0)} 字
      ${quota.max_usd != null ? `· 硬配额 $${esc(quota.max_usd)}` : "· 未设硬配额"}
    </p>
  `;
}

function quotaBar(quota, estimated) {
  if (!quota || quota.max_usd == null) {
    return `<p class="muted">未设置 QUOTA_MAX_USD。软配额 ${quota?.soft_usd ?? "关闭"}。</p>`;
  }
  const max = Number(quota.max_usd) || 0;
  const used = Number(estimated || quota.estimated_usd || 0);
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  const cls = quota.hard_exceeded ? "fail" : quota.soft_exceeded ? "warn" : "ok";
  return `
    <div class="quota">
      <div class="quota-track"><div class="quota-fill ${cls}" style="width:${pct}%"></div></div>
      <div class="muted">已用 $${esc(money(used))} / 硬上限 $${esc(money(max, 2))}（${pct}%）</div>
    </div>
  `;
}

function budgetView() {
  const budget = state.budget || {};
  const units = budget.units || {};
  const prices = budget.prices || state.usage?.prices || {};
  const quota = budget.quota || state.usage?.quota || {};
  const last = budget.last_run || {};
  const warn = quota.warning
    ? `<div class="banner ${quota.hard_exceeded ? "error" : "info"}">${esc(quota.warning)}</div>`
    : "";
  return `
    <section class="card">
      <h3>配额 / 成本账本</h3>
      ${warn}
      ${quotaBar(quota, budget.estimated_usd)}
      <div class="stat-grid">
        <div><b>USD</b><span>${esc(money(budget.estimated_usd))}</span></div>
        <div><b>CNY</b><span>${esc(money(budget.estimated_cny))}</span></div>
        <div><b>已记录 USD</b><span>${esc(money(budget.recorded_usd))}</span></div>
        <div><b>本轮 USD</b><span>${esc(money(last.estimated_usd))}</span></div>
        <div><b>token</b><span>${esc(units.tokens || 0)}</span></div>
        <div><b>图像</b><span>${esc(units.images || 0)}</span></div>
        <div><b>视频秒</b><span>${esc(units.video_seconds || 0)}</span></div>
        <div><b>TTS 字</b><span>${esc(units.tts_chars || 0)}</span></div>
      </div>
      <p class="muted">
        单价：token $${esc(prices.token_per_1k_usd ?? "0.00015")}/1k ·
        图 $${esc(prices.image_usd ?? "0.04")} ·
        视频 $${esc(prices.video_per_second_usd ?? "0.10")}/s ·
        TTS $${esc(prices.tts_per_1k_chars_usd ?? "0.015")}/1k 字 ·
        汇率 ${esc(prices.fx_cny_per_usd ?? "7.2")}
      </p>
      <p class="muted">mock 引擎费用记 0，不受硬配额拦截。live 引擎超 QUOTA_MAX_USD 时拒绝入队。</p>
    </section>
  `;
}

function reviewStatusChip(status) {
  const kind = status === "passed" ? "ok" : status === "rejected" ? "fail" : "warn";
  const labels = {
    pending: "待审",
    passed: "通过",
    revise: "返工",
    rejected: "拒绝",
    unreviewed: "未审",
  };
  return `<span class="chip ${kind}">${esc(labels[status] || status)}</span>`;
}

function issueSummary(issues) {
  const list = issues || [];
  if (!list.length) return "—";
  return list
    .slice(0, 3)
    .map((item) => item.message || item.suggestion || "")
    .filter(Boolean)
    .map((text) => esc(text))
    .join("；");
}

function scoreSummary(scores) {
  const entries = Object.entries(scores || {});
  if (!entries.length) return "—";
  return entries.map(([key, value]) => `${esc(key)} ${esc(value)}`).join(" · ");
}

function historyBlock(history) {
  const rows = (history || [])
    .map(
      (item) =>
        `<li>第 ${esc(item.attempt)} 次 · ${esc(item.action)} · ${esc(item.reviewer || "—")} · ${esc(fmtTime(item.created_at))}</li>`,
    )
    .join("");
  return rows ? `<ol class="history">${rows}</ol>` : `<p class="muted">尚无审核记录</p>`;
}

function reviewDeskView() {
  const desk = state.reviews;
  const project = state.project;
  if (!desk || !project) {
    return `
      <section class="card">
        <h3>审核台</h3>
        <p class="empty">还没有可审目标。先跑一遍流水线。</p>
      </section>
    `;
  }
  const filter = state.reviewFilter;
  const targets = (desk.targets || []).filter((row) => {
    if (filter === "pending") return row.status === "pending" || row.status === "revise";
    if (filter === "failed") return row.status === "rejected";
    return true;
  });
  const rows = targets
    .map((row) => {
      const type = row.target_type;
      return `
        <tr>
          <td>${esc(type)}<div class="muted">${esc(row.target_id)}</div></td>
          <td>${esc(row.label)}</td>
          <td>${reviewStatusChip(row.status)}</td>
          <td>${esc(row.attempts)} / r${esc(row.revision)}</td>
          <td>${scoreSummary(row.scores)}</td>
          <td>${issueSummary(row.issues)}</td>
          <td>
            <div class="mini-actions">
              <button class="btn" data-action="override-target" data-id="${esc(row.target_id)}" data-type="${esc(type)}" data-verdict="pass">通过</button>
              <button class="btn" data-action="override-target" data-id="${esc(row.target_id)}" data-type="${esc(type)}" data-verdict="revise">返工</button>
              <button class="btn" data-action="override-target" data-id="${esc(row.target_id)}" data-type="${esc(type)}" data-verdict="reject">拒绝</button>
            </div>
            <div class="muted">覆盖后重跑「${esc(STAGE_LABELS[row.rerun_stage] || row.rerun_stage)}」</div>
            ${historyBlock(row.history)}
          </td>
        </tr>`;
    })
    .join("");
  return `
    <section class="card">
      <div class="row">
        <h3>审核台</h3>
        <div class="chips">
          <button type="button" class="genre-chip${filter === "pending" ? " active" : ""}" data-action="review-filter" data-filter="pending">待审 ${esc(desk.pending || 0)}</button>
          <button type="button" class="genre-chip${filter === "failed" ? " active" : ""}" data-action="review-filter" data-filter="failed">失败 ${esc(desk.failed || 0)}</button>
          <button type="button" class="genre-chip${filter === "all" ? " active" : ""}" data-action="review-filter" data-filter="all">全部 ${esc((desk.targets || []).length)}</button>
        </div>
      </div>
      <p class="muted">按章节 / 分镜 / 资产 / 片段列出待审与失败项。覆盖写入现有 override API，再点运行即可从对应阶段续跑。</p>
      <div class="grid-2">
        <div class="field">
          <span>覆盖原因</span>
          <input id="desk-reason" type="text" value="${esc(state.overrideReason)}" />
        </div>
        <div class="field">
          <span>批量</span>
          <div class="actions">
            <button class="btn primary" data-action="pass-pending" ${state.busy || !desk.pending ? "disabled" : ""}>全部待审通过</button>
            <button class="btn" data-action="run" ${state.busy ? "disabled" : ""}>覆盖后运行流水线</button>
          </div>
        </div>
      </div>
      ${
        rows
          ? `<table>
              <thead><tr><th>目标</th><th>名称</th><th>状态</th><th>次数/修订</th><th>分数</th><th>问题</th><th>覆盖 / 历史</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : `<p class="empty">${filter === "all" ? "还没有审核目标。" : "这一栏是空的。"}</p>`
      }
    </section>
  `;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail) detail = JSON.stringify(data.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  const type = res.headers.get("content-type") || "";
  return type.includes("application/json") ? res.json() : res.text();
}

async function loadGenres() {
  if (state.genres) return state.genres;
  state.genres = await api("/genres");
  if (state.genres.presets?.length) state.genrePick = state.genres.presets[0];
  return state.genres;
}

async function loadList() {
  state.projects = await api("/projects");
  try {
    state.usage = await api("/usage");
  } catch {
    state.usage = null;
  }
}

async function loadDetail(id) {
  state.project = await api(`/projects/${id}`);
  const extras = await Promise.allSettled([
    api(`/projects/${id}/exports`),
    api(`/projects/${id}/budget`),
    api(`/projects/${id}/reviews`),
    api("/usage"),
  ]);
  state.exports = extras[0].status === "fulfilled" ? extras[0].value : null;
  state.budget = extras[1].status === "fulfilled" ? extras[1].value : null;
  state.reviews = extras[2].status === "fulfilled" ? extras[2].value : null;
  state.usage = extras[3].status === "fulfilled" ? extras[3].value : state.usage;
}

function render() {
  const app = document.getElementById("app");
  app.innerHTML = `
    <div class="shell">
      <header class="topbar">
        <div class="brand">
          <small>AI Novel Drama Factory</small>
          <h1>短剧工厂工作台</h1>
        </div>
        <nav>
          <a class="btn" href="#/">项目列表</a>
          <a class="btn primary" href="#/new">新建项目</a>
        </nav>
      </header>
      ${state.error ? `<div class="banner error">${esc(state.error)}</div>` : ""}
      ${state.notice ? `<div class="banner info">${esc(state.notice)}</div>` : ""}
      ${view()}
    </div>
  `;
}

function view() {
  if (state.route.name === "create") return createView();
  if (state.route.name === "detail") return detailView();
  return listView();
}

function listView() {
  const rows = state.projects
    .map(
      (item) => `
      <tr>
        <td><a href="#/p/${esc(item.id)}">${esc(item.title)}</a><div class="muted">${esc(item.id)}</div></td>
        <td><span class="chip">${esc(item.genre)}</span></td>
        <td>${esc(LICENSE_LABELS[item.license_status] || item.license_status)}</td>
        <td>${stageChip(item.stage)}</td>
        <td class="num">$${esc(money(item.estimated_usd))}</td>
        <td>${esc(fmtTime(item.updated_at))}</td>
        <td><a class="btn" href="#/p/${esc(item.id)}">打开</a></td>
      </tr>`,
    )
    .join("");
  return `
    <section class="card">
      <div class="row">
        <h2>项目列表</h2>
        <a class="btn primary" href="#/new">新建项目</a>
      </div>
      <p class="muted">默认 mock 引擎，无需 Redis / API 密钥。创建后可运行全流程并查看导出。</p>
      ${usageStrip()}
      ${
        rows
          ? `<table>
              <thead><tr><th>标题</th><th>题材</th><th>版权</th><th>阶段</th><th>估算</th><th>更新</th><th></th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : `<p class="empty">还没有项目。先<a href="#/new">新建</a>一个 mock 短剧。</p>`
      }
    </section>
  `;
}

function createView() {
  const genres = state.genres || { presets: [], license_status: [], rights_disclaimer: "" };
  const chips = (genres.presets || [])
    .map(
      (name) =>
        `<button type="button" class="genre-chip${state.genrePick === name ? " active" : ""}" data-action="pick-genre" data-genre="${esc(name)}">${esc(name)}</button>`,
    )
    .join("");
  const licenses = (genres.license_status || ["unknown", "original", "licensed"])
    .map((item) => `<option value="${esc(item)}">${esc(LICENSE_LABELS[item] || item)}</option>`)
    .join("");
  return `
    <section class="card">
      <h2>新建项目</h2>
      <p class="disclaimer">${esc(genres.rights_disclaimer || "")}</p>
      <form id="create-form">
        <div class="field">
          <span>标题</span>
          <input name="title" type="text" required maxlength="120" placeholder="例如：雨夜便利店" />
        </div>
        <div class="field">
          <span>梗概</span>
          <textarea name="premise" required placeholder="一句话到一小段都可以。会写入题材风格提示。"></textarea>
        </div>
        <div class="grid-2">
          <div class="field">
            <span>总字数</span>
            <input name="total_words" type="number" min="1" step="1" value="6000" required />
          </div>
          <div class="field">
            <span>版权状态（文档占位）</span>
            <select name="license_status">${licenses}</select>
          </div>
        </div>
        <div class="field">
          <span>题材预设</span>
          <div class="genre-row">${chips}</div>
        </div>
        <div class="field">
          <span>或自由填写题材</span>
          <input name="genre_free" type="text" placeholder="留空则使用上方预设，例如：都市甜宠" />
        </div>
        <div class="field">
          <span>版权备注（可选）</span>
          <input name="rights_note" type="text" placeholder="仅作项目文档，不构成法律意见" />
        </div>
        <div class="actions">
          <button class="btn primary" type="submit" ${state.busy ? "disabled" : ""}>创建项目</button>
          <a class="btn" href="#/">取消</a>
        </div>
      </form>
    </section>
  `;
}

function detailView() {
  const project = state.project;
  if (!project) return `<section class="card"><p>正在读取项目…</p></section>`;
  const overrides = project.metadata?.review_overrides || {};
  const currentStage = project.stage;
  const stages = STAGES.map((name) => {
    const idx = STAGES.indexOf(name);
    const cur = STAGES.indexOf(currentStage);
    let cls = "stage";
    if (currentStage === name) cls += " now";
    else if (currentStage === "done" || (cur > idx && cur !== -1)) cls += " done";
    return `<div class="${cls}"><b>${String(idx + 1).padStart(2, "0")}</b>${esc(STAGE_LABELS[name])}</div>`;
  }).join("");
  const chapters = (project.chapters || [])
    .map(
      (ch) =>
        `<tr><td>${ch.index}</td><td>${esc(ch.title)}</td><td>${ch.word_count}</td><td>${ch.revision}</td></tr>`,
    )
    .join("");
  const shotCount =
    state.exports?.shot_count ??
    (project.storyboards || []).reduce((n, sb) => n + (sb.shots || []).length, 0);
  const episodes = (project.episodes || [])
    .map(
      (ep) =>
        `<tr><td>${esc(ep.title)}</td><td>${esc(ep.kind)}</td><td>${esc(ep.duration_s)}s</td><td>${esc(ep.path || "—")}</td><td>${esc(ep.concat_path || "—")}</td></tr>`,
    )
    .join("");
  const exp = state.exports;
  const files = (exp?.files || [])
    .map((file) => `<li>${esc(file.name)} · ${file.available ? "可读" : "尚未生成"} · <code>${esc(file.relative_path)}</code></li>`)
    .join("");
  const job = state.job;
  return `
    <section class="card">
      <div class="row">
        <div>
          <h2>${esc(project.title)}</h2>
          <div class="muted">${esc(project.id)}</div>
        </div>
        ${stageChip(project.stage)}
      </div>
      <div class="meta">
        <span class="chip">${esc(project.genre)}</span>
        <span class="chip">${esc(LICENSE_LABELS[project.license_status] || project.license_status)}</span>
        <span class="chip">${esc(project.total_words)} 字</span>
        <span class="chip">${(project.chapters || []).length} 章</span>
        <span class="chip">${shotCount} 镜</span>
      </div>
      <p>${esc(project.premise)}</p>
      ${project.rights_note ? `<p class="disclaimer">版权备注：${esc(project.rights_note)}</p>` : ""}
      ${project.failure_reason ? `<div class="banner error">${esc(project.failure_reason)}</div>` : ""}
      <div class="stages">${stages}</div>
      <div class="actions">
        <button class="btn primary" data-action="run" ${state.busy ? "disabled" : ""}>运行流水线</button>
        <button class="btn" data-action="refresh" ${state.busy ? "disabled" : ""}>刷新状态</button>
      </div>
      ${
        job
          ? `<p class="muted">任务 ${esc(job.id)} · ${esc(job.status)} · 后端 ${esc(job.backend || "memory")}${job.error ? " · " + esc(job.error) : ""}</p>`
          : `<p class="muted">无 Redis 时运行是同步的，点一次就会跑完整条 mock 流水线。</p>`
      }
    </section>
    ${budgetView()}
    ${reviewDeskView()}
    <section class="card">
      <h3>全局 / 手工覆盖</h3>
      <p class="muted">写入后下次运行生效。覆盖会跳过模型与规则加严，审核记录标记为 human-override。优先用上方审核台按目标覆盖。</p>
      <form id="override-form">
        <div class="grid-2">
          <div class="field">
            <span>结论</span>
            <select name="action" required>
              <option value="pass">通过 pass</option>
              <option value="revise">返工 revise</option>
              <option value="reject">拒绝 reject</option>
            </select>
          </div>
          <div class="field">
            <span>目标类型（可选，空=全局）</span>
            <select name="target_type">
              <option value="">全局</option>
              <option value="chapter">章节 chapter</option>
              <option value="storyboard">分镜 storyboard</option>
              <option value="asset">资产 asset</option>
              <option value="clip">镜头 clip</option>
            </select>
          </div>
        </div>
        <div class="grid-2">
          <div class="field">
            <span>目标 id（可选）</span>
            <input name="target_id" type="text" placeholder="例如 chapter / shot / clip id" />
          </div>
          <div class="field">
            <span>原因</span>
            <input name="reason" type="text" value="人工覆盖" />
          </div>
        </div>
        <button class="btn primary" type="submit" ${state.busy ? "disabled" : ""}>保存覆盖</button>
      </form>
      <pre class="code">${esc(JSON.stringify(overrides, null, 2) || "{}")}</pre>
    </section>
    <section class="card">
      <h3>结果</h3>
      <p class="muted">章节 ${esc((project.chapters || []).length)} · 镜头 ${esc(shotCount)} · 片段 ${esc((project.clips || []).length)} · 剧集 ${esc((project.episodes || []).length)}</p>
      <h3>章节摘要</h3>
      ${
        chapters
          ? `<table><thead><tr><th>#</th><th>标题</th><th>字数</th><th>修订</th></tr></thead><tbody>${chapters}</tbody></table>`
          : `<p class="empty">流水线还没写出章节。</p>`
      }
      <h3>剧集 / 预算</h3>
      ${
        episodes
          ? `<table><thead><tr><th>剧集</th><th>类型</th><th>时长</th><th>路径</th><th>concat</th></tr></thead><tbody>${episodes}</tbody></table>`
          : `<p class="empty">尚无剧集包。</p>`
      }
      <p class="muted">账本估算 USD ${esc(money(project.budget?.estimated_usd))} / CNY ${esc(money(project.budget?.estimated_cny))} · 审核 ${esc((project.reviews || []).length)} 条</p>
      ${files ? `<ul>${files}</ul>` : ""}
      ${exp?.play_md ? `<h3>PLAY.md</h3><pre class="code">${esc(exp.play_md)}</pre>` : ""}
      ${
        exp?.budget_json
          ? `<h3>budget.json</h3><pre class="code">${esc(JSON.stringify(exp.budget_json, null, 2))}</pre>`
          : ""
      }
    </section>
  `;
}

async function bootRoute() {
  state.route = parseRoute();
  state.error = "";
  state.notice = "";
  try {
    await loadGenres();
    if (state.route.name === "list") {
      state.project = null;
      state.exports = null;
      await loadList();
    } else if (state.route.name === "detail") {
      await loadDetail(state.route.id);
    }
  } catch (err) {
    state.error = err.message || String(err);
  }
  render();
}

async function createProject(form) {
  const data = new FormData(form);
  const free = String(data.get("genre_free") || "").trim();
  const payload = {
    title: String(data.get("title") || "").trim(),
    premise: String(data.get("premise") || "").trim(),
    total_words: Number(data.get("total_words") || 0),
    genre: free || state.genrePick,
    license_status: String(data.get("license_status") || "unknown"),
    rights_note: String(data.get("rights_note") || "").trim(),
  };
  state.busy = true;
  state.error = "";
  render();
  try {
    const created = await api("/projects", { method: "POST", body: JSON.stringify(payload) });
    location.hash = `#/p/${created.id}`;
  } catch (err) {
    state.error = err.message || String(err);
  } finally {
    state.busy = false;
    render();
  }
}

function deskReason() {
  const input = document.getElementById("desk-reason");
  if (input && "value" in input) state.overrideReason = String(input.value || "人工覆盖");
  return state.overrideReason || "人工覆盖";
}

async function postOverride(payload) {
  if (!state.project) return;
  state.busy = true;
  state.error = "";
  render();
  try {
    await api(`/projects/${state.project.id}/override`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.notice = "覆盖已保存。点「运行流水线」从对应审核阶段续跑。";
    await loadDetail(state.project.id);
  } catch (err) {
    state.error = err.message || String(err);
  } finally {
    state.busy = false;
    render();
  }
}

async function saveOverride(form) {
  if (!state.project) return;
  const data = new FormData(form);
  const targetType = String(data.get("target_type") || "").trim();
  const targetId = String(data.get("target_id") || "").trim();
  const payload = {
    action: String(data.get("action") || "pass"),
    reason: String(data.get("reason") || "人工覆盖"),
  };
  if (targetType) payload.target_type = targetType;
  if (targetId) payload.target_id = targetId;
  await postOverride(payload);
}

async function runPipeline() {
  if (!state.project) return;
  state.busy = true;
  state.error = "";
  state.notice = "流水线运行中…";
  render();
  try {
    const job = await api(`/projects/${state.project.id}/run`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    state.job = job;
    if (job.status === "queued" || job.status === "running") {
      await pollJob(job.id, state.project.id);
    } else {
      await loadDetail(state.project.id);
    }
    state.notice =
      state.job?.status === "succeeded"
        ? "流水线完成。下方是审核台 / 章节 / 剧集 / 账本。"
        : state.job?.error || state.job?.warning || "任务已结束。";
    if (state.job?.warning && state.job?.status === "succeeded") {
      state.notice += ` ${state.job.warning}`;
    }
  } catch (err) {
    state.error = err.message || String(err);
    state.notice = "";
  } finally {
    state.busy = false;
    render();
  }
}

async function pollJob(jobId, projectId) {
  for (let i = 0; i < 180; i += 1) {
    state.job = await api(`/jobs/${jobId}`);
    await loadDetail(projectId);
    render();
    if (state.job.status === "succeeded" || state.job.status === "failed") return;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("等待任务超时，请手动刷新。");
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (action === "pick-genre") {
    state.genrePick = target.dataset.genre || state.genrePick;
    document.querySelectorAll(".genre-chip").forEach((el) => {
      el.classList.toggle("active", el.dataset.genre === state.genrePick);
    });
  } else if (action === "run") {
    runPipeline();
  } else if (action === "review-filter") {
    state.reviewFilter = target.dataset.filter || "pending";
    state.overrideReason = deskReason();
    render();
  } else if (action === "override-target") {
    postOverride({
      action: target.dataset.verdict || "pass",
      target_id: target.dataset.id,
      target_type: target.dataset.type,
      reason: deskReason(),
    });
  } else if (action === "pass-pending") {
    postOverride({
      action: "pass",
      pass_pending: true,
      reason: deskReason() || "pass all pending",
    });
  } else if (action === "refresh" && state.project) {
    loadDetail(state.project.id).then(render).catch((err) => {
      state.error = err.message || String(err);
      render();
    });
  }
});

document.addEventListener("submit", (event) => {
  if (event.target.id === "create-form") {
    event.preventDefault();
    createProject(event.target);
  }
  if (event.target.id === "override-form") {
    event.preventDefault();
    saveOverride(event.target);
  }
});

window.addEventListener("hashchange", bootRoute);
bootRoute();
