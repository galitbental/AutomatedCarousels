/* Carousel Studio UI — vanilla JS, no build step. Layout ported from the Stitch project "Carousel Studio". */
"use strict";

const STAGES = ["intake", "facts", "plan", "images", "slides", "final"];
const STAGE_LABEL = { intake: "Intake", facts: "Facts", plan: "Plan", images: "Images", slides: "Slides", final: "Final" };
const state = { view: "queue", sku: null, data: null, stage: null, sel: 1, logAfter: 0, bust: Date.now(),
  planDraft: null, expanded: {} };

/* ------------------------------------------------------------------ helpers */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (sel) => document.querySelector(sel);
const fileUrl = (rel) => `/file?path=${encodeURIComponent(rel)}&t=${state.bust}`;
const J = () => state.data && state.data.job;
const C = () => state.data && state.data.context;
const sku = () => state.sku;
const enc = encodeURIComponent;
const pad = (n) => String(n).padStart(2, "0");

function thumb(rel, cls, caption) {
  if (!rel) return h("div", { class: "empty" }, "No image");
  return h("img", { class: "thumb " + (cls || ""), src: fileUrl(rel), alt: rel, loading: "lazy",
    onclick: (e) => { e.stopPropagation(); lightbox(fileUrl(rel), caption || rel); } });
}
function lightbox(url, cap) {
  const lb = $("#lightbox");
  lb.querySelector("img").src = url;
  lb.querySelector(".lb-cap").textContent = cap || "";
  lb.classList.remove("hidden");
}

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
  const r = await fetch(url, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  if (!r.ok) {
    const err = new Error((data && data.error) || `${r.status} ${r.statusText}`);
    err.data = data; err.status = r.status;
    throw err;
  }
  return data;
}
function toast(msg, kind) {
  const t = h("div", { class: "toast " + (kind || "") }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "error" ? 9000 : 4000);
}
function modal(title, body, buttons, cls) {
  return new Promise((resolve) => {
    const m = $("#modal");
    m.innerHTML = "";
    const close = (v) => { m.classList.add("hidden"); m.innerHTML = ""; resolve(v); };
    m.append(h("div", { class: "dialog " + (cls || "") }, h("h2", {}, title),
      typeof body === "string" ? h("p", {}, body) : body,
      h("div", { class: "row", style: { justifyContent: "flex-end", marginTop: "16px" } },
        buttons.map((b) => h("button", { class: "btn " + (b.cls || ""), id: b.id, onclick: () => close(b.value) }, b.label)))));
    m.classList.remove("hidden");
  });
}
const confirmBox = (title, body, ok, danger) => modal(title, body, [
  { label: "Cancel", value: false }, { label: ok || "OK", value: true, cls: danger ? "danger" : "primary", id: "modal-ok" }]);
async function guard(fn) { try { return await fn(); } catch (e) { toast(e.message, "error"); return null; } }
function field(label, input, extra) { return h("div", {}, h("label", { class: "f" }, label), input, extra || null); }
function cardTitle(title, ...right) { return h("div", { class: "card-title" }, h("h3", { class: "grow" }, title), right); }
function seg(id, options, value, onPick, disabled) {
  return h("div", { class: "seg", id }, options.map(([v, label]) => h("button", { class: value === v ? "on" : "", "data-v": v,
    disabled: disabled ? true : null, onclick: (e) => {
      if (disabled) return;
      e.currentTarget.parentElement.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === e.currentTarget));
      onPick(v);
    } }, label)));
}
function statusRow(kind, title, detail) {
  return h("div", { class: "statusrow " + kind }, h("span", { class: "ic" }, kind === "ok" ? "✓" : "!"),
    h("div", {}, h("b", {}, title), detail ? h("span", { class: "muted small" }, detail) : null));
}

/* ------------------------------------------------------------------ bell */
let audio = null;
function unlockAudio() {
  // Chrome only lets a page play sound after a click, so the audio context is created/resumed on clicks
  try { audio = audio || new AudioContext(); if (audio.state === "suspended") audio.resume(); } catch (e) { audio = null; }
}
function bell() {
  unlockAudio();
  if (!audio) return;
  const t0 = audio.currentTime + 0.05;
  const out = audio.createGain();
  out.gain.value = 0.16;
  out.connect(audio.destination);
  // two soft strikes of a small bell: inharmonic partials, each fading at its own speed
  [[0, 1568], [0.42, 2093]].forEach(([at, f]) => {
    [[1, 1, 2.6], [2.76, 0.32, 1.2], [5.4, 0.12, 0.6], [8.93, 0.05, 0.35]].forEach(([ratio, amp, decay]) => {
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = "sine";
      o.frequency.value = f * ratio;
      g.gain.setValueAtTime(0, t0 + at);
      g.gain.linearRampToValueAtTime(amp, t0 + at + 0.006);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + at + decay);
      o.connect(g); g.connect(out);
      o.start(t0 + at); o.stop(t0 + at + decay + 0.05);
    });
  });
}
const BELL_TASKS = /^gen:all$/;  // hook: ring when "Generate all missing" finishes

/* ------------------------------------------------------------------ tasks & log */
const watchers = {};
const finished = new Set();  // a stale job view may still list a task that already finished
function watchTask(task, onDone) {
  if (!task || !task.id || finished.has(task.id)) return;
  watchers[task.id] = onDone || (() => reloadJob(true));
  renderTasks();
}
async function pollTasks() {
  for (const id of Object.keys(watchers)) {
    let t;
    try { t = await api("GET", `/api/tasks/${id}`); } catch (e) { delete watchers[id]; continue; }
    if (t.status === "running" || !watchers[id]) continue;  // still running, or handled by an overlapping poll
    const cb = watchers[id];
    delete watchers[id];
    finished.add(id);
    if (BELL_TASKS.test(t.kind) && t.status !== "cancelled" && !(state.settings && state.settings.bell_sound === false)) bell();
    if (t.status === "done") toast(`Done: ${t.label}`, "ok");
    else if (t.status === "cancelled") toast(`Cancelled: ${t.label}`);
    else toast(`Failed: ${t.label}: ${t.error}`, "error");
    state.bust = Date.now();
    try { await cb(t); } catch (e) { console.error(e); }
  }
}
let runningTasks = [];
function renderTasks() {
  const box = $("#tasks");
  if (!box) return;
  box.innerHTML = "";
  for (const t of runningTasks) {
    box.append(h("div", { class: "taskchip" }, h("span", { class: "spin" }),
      `${t.label} · ${Math.round(t.elapsed)}s`,
      h("button", { title: "Cancel", onclick: () => guard(() => api("POST", `/api/tasks/${t.id}/cancel`)) }, "✕")));
  }
}
async function pollLog() {
  try {
    const d = await api("GET", `/api/log?after=${state.logAfter}`);
    runningTasks = d.tasks;
    renderTasks();
    const list = $("#loglist");
    for (const e of d.items) {
      state.logAfter = e.id;
      list.append(h("div", { class: "lg " + e.level }, h("span", { class: "t" }, e.ts + " "),
        e.sku ? h("span", { class: "s" }, e.sku + " ") : null, e.msg));
      $("#loglast").textContent = `${e.ts}  ${e.sku ? e.sku + ": " : ""}${e.msg}`;
    }
    if (d.items.length) list.scrollTop = list.scrollHeight;
  } catch (e) { /* server restarting */ }
}

/* ------------------------------------------------------------------ autosave */
let pending = {}, saveTimer = null;
function merge(dst, src) {
  for (const [k, v] of Object.entries(src)) {
    if (v && typeof v === "object" && !Array.isArray(v)) { dst[k] = dst[k] || {}; merge(dst[k], v); }
    else dst[k] = v;
  }
}
function queueSave(patch, delay) {
  merge(pending, patch);
  clearTimeout(saveTimer);
  setSaveState("Saving…");
  saveTimer = setTimeout(flushSave, delay === undefined ? 600 : delay);
}
async function flushSave() {
  clearTimeout(saveTimer);
  if (!Object.keys(pending).length) return true;
  const p = pending; pending = {};
  try {
    const d = await api("PATCH", `/api/jobs/${enc(sku())}`, p);
    state.data = d;
    setSaveState("Saved");
    refreshChecks();
    if (["plan", "slides", "images"].includes(state.stage)) refreshPreviews(state.sel);
    return true;
  } catch (e) { toast(e.message, "error"); setSaveState("Not saved"); return false; }
}
function setSaveState(t) {
  const el = $("#savestate"); if (el) el.textContent = t === "Saved" ? "Changes are saved automatically" : t;
  const p = $("#savepill"); if (p) { p.textContent = t === "Saving…" ? "Saving…" : t === "Not saved" ? "Not saved" : "Draft saved"; }
}

/* ------------------------------------------------------------------ navigation */
function setActiveNav() {
  document.querySelectorAll(".nav").forEach((b) => b.classList.remove("active"));
  if (state.view === "job") { const b = document.querySelector(`[data-sku="${CSS.escape(state.sku)}"]`); if (b) b.classList.add("active"); }
  else { const b = $(`#nav-${state.view}`); if (b) b.classList.add("active"); }
}
function plainTopbar(title) {
  const tb = $("#topbar");
  tb.innerHTML = "";
  tb.append(h("div", { id: "crumb" }, title), h("div", { id: "tasks" }));
  renderTasks();
}
async function go(view, arg) {
  if (state.view === "job") await flushSave();
  state.view = view;
  if (view === "job") { state.sku = arg; state.stage = null; state.sel = 1; await reloadJob(); }
  else if (view === "queue") await showQueue();
  else if (view === "library") await showLibrary();
  else if (view === "settings") await showSettings();
  else if (view === "system") await showSystem();
  setActiveNav();
}
async function refreshSideJobs() {
  const q = await api("GET", "/api/queue");
  const box = $("#nav-jobs");
  box.innerHTML = "";
  for (const j of q.jobs) {
    box.append(h("button", { class: "nav", "data-sku": j.sku, onclick: () => go("job", j.sku) },
      h("span", { class: "ico" }, "◆"), h("span", {}, j.sku, h("span", { class: "sub" }, `${STAGE_LABEL[j.stage] || j.stage} · in progress`)),
      h("span", { class: "dot" })));
  }
  const ready = q.inputs.filter((i) => i.status === "ready").length;
  $("#queue-count").textContent = ready ? String(ready) : "";
  setActiveNav();
  return q;
}

/* ------------------------------------------------------------------ queue */
async function showQueue() {
  plainTopbar("Queue");
  const q = await refreshSideJobs();
  const v = $("#view");
  v.innerHTML = "";
  const page = h("div", { class: "page" });
  v.append(page);
  page.append(h("div", { class: "row" },
    h("div", { class: "grow" }, h("div", { class: "rule" }), h("h2", { style: { marginBottom: "2px" } }, "Photos waiting for a carousel"),
      h("div", { class: "muted" }, "Product photos named by SKU in DataFromUser")),
    h("button", { class: "btn", id: "btn-refresh", onclick: () => showQueue() }, "↻ Refresh"),
    h("button", { class: "btn", onclick: () => guard(() => api("POST", "/api/open", { path: "DataFromUser" })) }, "Open folder")));

  if (q.jobs.length) {
    page.append(h("div", { class: "section-title" }, h("h3", {}, "In progress"), h("span", { class: "count" }, q.jobs.length)));
    for (const j of q.jobs) {
      const done = STAGES.filter((s) => j.stages[s] === "approved").length;
      page.append(h("div", { class: "wide", id: `job-${j.sku}` }, thumb(j.input_file, "", j.sku),
        h("div", { class: "grow" }, h("div", { class: "sku" }, j.sku), h("div", { class: "muted small" }, j.jewelry_type)),
        h("div", {}, h("div", { class: "dots" }, STAGES.map((s, i) => h("i", { class: i < done ? "done" : i === done ? "cur" : "" }))),
          h("div", { class: "small muted", style: { marginTop: "4px" } }, `At ${STAGE_LABEL[j.stage] || j.stage}`)),
        h("button", { class: "btn primary", id: `resume-${j.sku}`, onclick: () => go("job", j.sku) }, "Resume →")));
    }
  }
  const ready = q.inputs.filter((i) => i.status === "ready");
  const blocked = q.inputs.filter((i) => i.status === "blocked");
  page.append(h("div", { class: "section-title" }, h("h3", {}, "Ready"), h("span", { class: "count" }, ready.length)));
  if (!q.inputs.length) page.append(h("div", { class: "card" }, "No photos in DataFromUser. Add a product photo named by its SKU, e.g. ",
    h("code", {}, "GodDaughter1_G_IC.jpg"), ", then click Refresh."));
  else if (!ready.length) page.append(h("div", { class: "muted" }, "Every photo is either in progress or blocked."));
  page.append(h("div", { class: "grid" }, ready.map((it) => h("div", { class: "qcard", id: `card-${it.sku}` }, thumb(it.file, "", it.sku),
    h("div", { class: "body" }, h("div", { class: "sku" }, it.sku), h("div", { class: "muted small" }, it.jewelry_type),
      h("div", { style: { marginTop: "auto", paddingTop: "8px" } },
        h("button", { class: "btn primary", id: `start-${it.sku}`, onclick: () => startJob(it.sku) }, "Start carousel")))))));
  if (blocked.length) {
    page.append(h("div", { class: "section-title" }, h("h3", {}, "Blocked"), h("span", { class: "count" }, blocked.length)));
    page.append(h("div", { class: "grid" }, blocked.map((it) => h("div", { class: "qcard blocked", id: `card-${it.sku}` }, thumb(it.file, "", it.sku),
      h("div", { class: "body" }, h("div", { class: "sku" }, it.sku), h("div", { class: "muted small" }, it.jewelry_type || "Unknown type"),
        h("div", { class: "msg err small" }, it.reason))))));
  }
  page.append(h("div", { style: { height: "40px" } }));
}
async function startJob(s) {
  const d = await guard(() => api("POST", "/api/jobs", { sku: s }));
  if (!d) return;
  await refreshSideJobs();
  go("job", s);
}

/* ------------------------------------------------------------------ job shell */
async function reloadJob(keepStage) {
  const d = await guard(() => api("GET", `/api/jobs/${enc(sku())}`));
  if (!d) { go("queue"); return; }
  state.data = d;
  state.bust = Date.now();
  if (!keepStage || !state.stage) state.stage = firstOpenStage();
  const ns = (d.job.plan.slides || []).map((s) => s.n);
  if (!ns.includes(state.sel)) state.sel = ns[0] || 1;
  renderJob();
}
function firstOpenStage() {
  const st = J().stages;
  return STAGES.find((s) => st[s] === "open" || st[s] === "stale") || "final";
}
function stageHint(s) {
  const job = J(), st = job.stages[s], slides = job.plan.slides || [];
  if (st === "approved") return s === "final" ? "Saved" : "Approved";
  if (st === "locked") return "—";
  if (s === "intake") return job.catalog && job.catalog.status === "found" ? "Review card" : "Fill in";
  if (s === "facts") return "Review facts";
  if (s === "plan") return slides.length ? `${slides.length} slides` : "Generate";
  if (s === "images") {
    const need = slides.filter((x) => x.source !== "none");
    return `${need.filter((x) => (job.images[String(x.n)] || { versions: [] }).versions.length).length}/${need.length} images`;
  }
  if (s === "slides") return Object.keys(job.render.dirty || {}).length || !Object.keys(job.render.files || {}).length ? "Render" : "Rendered";
  return "Approve & save";
}
function jobTopbar() {
  const job = J(), ctx = C();
  const tb = $("#topbar");
  tb.innerHTML = "";
  tb.append(h("div", { class: "jobtitle" }, thumb(job.input_file, "", job.sku),
    h("div", {}, h("span", { class: "name" }, job.sku), " ",
      h("span", { class: "meta" }, `· ${ctx.style.name} · ${job.sku_info.metal}`,
        job.sku_info.birth_month_name ? ` · ${job.sku_info.birth_month_name}` : ""))),
    h("span", { class: "pill ok", id: "savepill" }, "Draft saved"),
    h("div", { id: "tasks" }),
    h("button", { class: "btn small danger", id: "btn-discard", onclick: discardJob }, "Discard job"));
  renderTasks();
}
function renderJob() {
  const job = J(), ctx = C();
  jobTopbar();
  const v = $("#view");
  const scroll = v.scrollTop;
  v.innerHTML = "";
  const stepper = h("div", { class: "stepper" });
  STAGES.forEach((s, i) => {
    const st = job.stages[s];
    if (i) stepper.append(h("div", { class: "step-line" + (job.stages[STAGES[i - 1]] === "approved" ? " done" : "") }));
    stepper.append(h("div", { class: `step ${st} ${s === state.stage ? "current" : ""}`, id: `step-${s}`, title: st,
      onclick: async () => { if (st !== "locked") { await flushSave(); state.stage = s; renderJob(); } } },
      h("span", { class: "dot" }, st === "approved" && s !== state.stage ? "✓" : st === "stale" ? "!" : i + 1),
      h("span", {}, h("span", { class: "lbl" }, STAGE_LABEL[s]), h("span", { class: "hint" }, st === "stale" ? "Re-approve" : stageHint(s)))));
  });
  v.append(stepper);
  const body = h("div", { id: "stagebody" });
  v.append(body);
  ({ intake: renderIntake, facts: renderFacts, plan: renderPlan, images: renderImages,
     slides: renderSlides, final: renderFinal })[state.stage](body);
  v.append(actionBar());
  v.scrollTop = scroll;
  (ctx.tasks || []).forEach((t) => { if (!watchers[t.id]) watchTask(t, () => reloadJob(true)); });
}
const editableStage = (s) => ["open", "stale"].includes(J().stages[s]);

function actionBar() {
  const s = state.stage, st = J().stages[s];
  const bar = h("div", { class: "actionbar" }, h("span", { class: "savestate grow", id: "savestate" },
    st === "approved" ? "This stage is approved. Reopen it to make changes." :
    st === "stale" ? "An earlier stage changed. Review and approve again." : "Changes are saved automatically"));
  if (st === "approved" && s !== "final") bar.append(h("button", { class: "btn", id: "btn-reopen", onclick: () => reopenStage(s) }, "Reopen to edit"));
  if (st !== "approved" && s !== "final")
    bar.append(h("button", { class: "btn primary", id: "btn-approve", onclick: () => approveStage(s) }, `Approve ${STAGE_LABEL[s]} →`));
  return bar;
}
async function approveStage(stage, force) {
  if (!(await flushSave())) return;
  try {
    state.data = await api("POST", `/api/jobs/${enc(sku())}/approve/${stage}`, { force: !!force });
    toast(`${STAGE_LABEL[stage]} approved`, "ok");
    state.stage = firstOpenStage();
    renderJob();
    refreshSideJobs();
  } catch (e) {
    if (e.data && e.data.needs_confirm) {
      if (await confirmBox("Please confirm", e.data.warnings.join("\n"), "Approve anyway")) approveStage(stage, true);
    } else toast(e.message, "error");
  }
}
async function reopenStage(stage) {
  const later = STAGES.slice(STAGES.indexOf(stage) + 1).filter((s) => J().stages[s] === "approved");
  if (later.length && !(await confirmBox("Reopen stage",
    `Reopening ${STAGE_LABEL[stage]} marks these approved stages for re-approval: ${later.map((s) => STAGE_LABEL[s]).join(", ")}.`, "Reopen"))) return;
  const d = await guard(() => api("POST", `/api/jobs/${enc(sku())}/reopen/${stage}`));
  if (d) { state.data = d; renderJob(); }
}
async function discardJob() {
  if (!(await confirmBox("Discard job", `Delete all work for ${sku()}? The input photo stays in DataFromUser.`, "Discard", true))) return;
  if (await guard(() => api("DELETE", `/api/jobs/${enc(sku())}`))) { toast("Job discarded"); await refreshSideJobs(); go("queue"); }
}
function runTask(url, body, onDone) {
  return guard(async () => { const t = await api("POST", url, body || {}); watchTask(t, onDone); return t; });
}

/* ------------------------------------------------------------------ storyboard + live preview (shared) */
function previewEl(n, width, id) {
  const scale = width / 1080;
  return h("div", { class: "preview", id: id || `pv-${n}`, style: { width: `${width}px`, height: `${Math.round(1350 * scale)}px` } },
    h("iframe", { src: `/api/jobs/${enc(sku())}/preview/${n}?t=${state.bust}`, style: { transform: `scale(${scale})` },
      tabindex: "-1", title: `Slide ${n} preview` }));
}
function refreshPreviews(n) {
  document.querySelectorAll(`#pv-${n} iframe, #sb-${n} iframe`).forEach((f) => {
    f.src = `/api/jobs/${enc(sku())}/preview/${n}?t=${Date.now()}`;
  });
}
function slideStatus(s, mode) {
  const job = J();
  const img = job.images[String(s.n)];
  const cur = img && img.versions.length ? img.versions[img.current] : null;
  if (mode === "slides" || mode === "final") {
    const done = (job.render.files || {})[String(s.n)] && !(job.render.dirty || {})[String(s.n)];
    return done ? ["ok", "Rendered"] : ["warn", "Needs render"];
  }
  if (s.source === "none") return ["none", "Black slide"];
  if (!cur) return mode === "images" ? ["warn", "Missing"] : ["warn", s.source];
  if (cur.qa && !cur.qa.ok) return ["err", "QA issue"];
  return ["ok", mode === "images" ? "Ready" : s.source];
}
function storyboard(mode, opts) {
  const job = J(), slides = job.plan.slides || [];
  const files = job.render.files || {};
  const strip = h("div", { class: "storyboard", id: "storyboard" });
  slides.forEach((s) => {
    const [st, label] = slideStatus(s, mode);
    const rendered = files[String(s.n)];
    const mini = (mode === "slides" || mode === "final") && rendered && !(job.render.dirty || {})[String(s.n)]
      ? h("img", { src: fileUrl(rendered) })
      : h("iframe", { src: `/api/jobs/${enc(sku())}/preview/${s.n}?t=${state.bust}`, tabindex: "-1",
          style: { width: "1080px", height: "1350px", transform: `scale(${112 / 1080})`, transformOrigin: "0 0" } });
    strip.append(h("div", { class: "sb" + (s.n === state.sel ? " sel" : ""), id: `sb-${s.n}`, title: s.purpose,
      onclick: async () => { if (s.n === state.sel) return; await flushSave(); state.sel = s.n; renderJob(); } },
      h("div", { class: "sbhead" }, h("span", { class: "n" }, pad(s.n)), h("span", {}, s.layout)),
      h("div", { class: "mini" }, mini),
      h("div", { class: "sbfoot" }, h("span", { class: "grow", style: { overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" } },
        mode === "plan" ? s.purpose : label), h("span", { class: "st " + st }))));
  });
  if (opts && opts.add) strip.append(opts.add);
  return strip;
}
function selectedSlide() { return (J().plan.slides || []).find((s) => s.n === state.sel) || (J().plan.slides || [])[0]; }
function slideNav() {
  const slides = J().plan.slides || [], i = slides.findIndex((s) => s.n === state.sel);
  const goTo = async (j) => { if (j < 0 || j >= slides.length) return; await flushSave(); state.sel = slides[j].n; renderJob(); };
  return h("div", { class: "pv-nav" },
    h("button", { class: "btn small", disabled: i <= 0, onclick: () => goTo(i - 1) }, "← Previous"),
    h("span", { class: "muted small" }, `Slide ${i + 1} of ${slides.length}`),
    h("button", { class: "btn small", disabled: i >= slides.length - 1, onclick: () => goTo(i + 1) }, "Next →"));
}

/* ------------------------------------------------------------------ stage 1: intake */
/* Chip row: selected values + a few suggestions, "+ more" for the full list, "+ add" for your own value. */
function multiSelect(id, values, options, onChange, ed, limit) {
  let selected = (values || []).slice();
  const wrap = h("div", { class: "multi", id });
  const draw = () => {
    wrap.innerHTML = "";
    const all = Array.from(new Set(selected.concat(options)));
    const open = state.expanded[id];
    const shown = all.filter((o, i) => selected.includes(o) || open || i < (limit || 99));
    shown.forEach((o) => wrap.append(h("span", {
      class: "opt" + (selected.includes(o) ? " on" : ""), "data-v": o,
      onclick: () => {
        if (!ed) return;
        selected = selected.includes(o) ? selected.filter((x) => x !== o) : selected.concat([o]);
        onChange(selected); draw();
      } }, selected.includes(o) ? "✓ " + o : o)));
    if (all.length > shown.length || open) wrap.append(h("span", { class: "opt more", id: id + "-more",
      onclick: () => { state.expanded[id] = !open; draw(); } }, open ? "less" : `+ ${all.length - shown.length} more…`));
    if (ed) wrap.append(h("input", { type: "text", class: "opt-add", id: id + "-add", placeholder: "+ add",
      list: id + "-dl", onkeydown: (e) => {
        const v = e.target.value.trim();
        if (e.key === "Enter" && v) { if (!selected.includes(v)) selected = selected.concat([v]); onChange(selected); draw();
          const n = document.getElementById(id + "-add"); if (n) n.focus(); }
      } }), h("datalist", { id: id + "-dl" }, all.map((o) => h("option", { value: o }))));
  };
  draw();
  return wrap;
}
function chipRow(label, el) { return h("div", { class: "chiprow" }, h("span", { class: "eyebrow-label" }, label), el); }

function catalogCard(ed) {
  const job = J(), cat = job.catalog || {};
  const base = `/api/jobs/${enc(sku())}/intake/catalog`;
  const choose = (key) => guard(async () => { state.data = await api("POST", base, key ? { key } : {}); toast(key ? "Card applied to the form" : "Catalog searched", "ok"); renderJob(); });
  const badge = { found: ["Found", "ok"], ambiguous: ["Please confirm", "warn"], not_found: ["Not found", "err"], unavailable: ["Catalog offline", "err"] }[cat.status] || ["Not searched", ""];
  const method = { poem: "matched by poem name", "poem+variant": "matched by poem name + variant", image: "matched by comparing images", "chosen by user": "chosen by you" }[cat.method] || "";
  const imgUrl = (name) => `/api/catalog/image?name=${enc(name)}`;
  return h("div", { class: "card", id: "catalog-panel" },
    cardTitle("Catalog poem card", h("span", { class: "pill " + badge[1], id: "catalog-status" }, badge[0])),
    h("div", { class: "photo-frame" }, h("img", { src: fileUrl(job.input_file), alt: "Input photo",
      onclick: () => lightbox(fileUrl(job.input_file), "Your product photo") }), h("span", { class: "tag" }, "Your product photo")),
    cat.chosen ? h("div", { class: "matched" },
      cat.image ? h("img", { src: imgUrl(cat.image), onclick: () => lightbox(imgUrl(cat.image), cat.chosen) }) : null,
      h("div", { class: "grow" }, h("div", { id: "catalog-chosen", style: { fontWeight: 700 } }, cat.chosen),
        h("div", { class: "muted small" }, method), cat.message ? h("div", { class: "small", style: { color: "var(--warn)" } }, cat.message) : null)) :
      h("div", { class: "msg " + (cat.status === "unavailable" ? "err" : "info") }, cat.message || "No catalog card linked yet."),
    (cat.candidates || []).length > 1 ? h("div", {}, h("label", { class: "f" }, "Other matching cards — click to use instead"),
      h("div", { class: "cand-row" }, cat.candidates.map((c) => h("div", { class: "cand" + (c.key === cat.chosen ? " cur" : ""), title: c.key,
        onclick: () => { if (ed && c.key !== cat.chosen) choose(c.key); } },
        c.image ? h("img", { src: imgUrl(c.image) }) : h("div", { class: "noimg" }, "no image"),
        h("div", {}, c.variant || "(generic)", c.similarity !== undefined ? h("span", { class: "muted" }, ` · ${Math.round(c.similarity * 100)}%`) : null))))) : null,
    h("div", { class: "row", style: { marginTop: "14px" } },
      h("button", { class: "btn small", id: "btn-catalog", disabled: !ed, onclick: () => choose(null) }, "↻ Search catalog again"),
      h("button", { class: "btn small", id: "btn-read-card", disabled: !ed,
        onclick: () => runTask(`/api/jobs/${enc(sku())}/intake/read`, {}, () => reloadJob(true)) }, "✦ Read card with Claude")));
}

function renderIntake(body) {
  const job = J(), it = job.intake, ed = editableStage("intake"), info = job.sku_info, ctx = C();
  const save = (k, v) => queueSave({ intake: { [k]: v } });
  const inp = (k, attrs) => h("input", Object.assign({ type: "text", id: `in-${k}`, value: it[k] || "", disabled: !ed,
    oninput: (e) => save(k, e.target.value) }, attrs || {}));
  const multi = (k, opts, limit) => multiSelect(`ms-${k}`, it[k] || [], opts, (v) => save(k, v), ed, limit);
  const sug = it.suggested || {};
  const skuRows = [["Poem name", info.poem_name], ["Metal", info.metal + (info.metal_raw ? ` (${info.metal_raw})` : "")],
    ["Type code", info.type_code], ["Jewelry type", info.jewelry_type],
    ["Birth month", info.birth_month_name ? `${info.birth_month_name} (${info.birth_color})` : null],
    ["Chain length", info.chain_length], ["Engraving style", info.engraving_style],
    ["Men / boys", info.men ? "yes" : null], ["Style folder", ctx.style.folder]].filter((r) => r[1]);

  const left = h("div", {}, catalogCard(ed),
    h("details", { class: "card", style: { marginTop: "18px" } }, h("summary", { style: { cursor: "pointer" } }, h("b", {}, "SKU details")),
      h("table", { class: "kv", style: { marginTop: "10px" } }, skuRows.map((r) => h("tr", {}, h("td", {}, r[0]), h("td", {}, r[1]))))));

  const right = h("div", {},
    h("div", { class: "card" },
      h("div", { class: "rule" }), cardTitle("Who, to whom, and why"),
      it.source ? h("div", { class: "msg info", id: "intake-source" }, h("span", {}, "ⓘ"),
        h("span", {}, "Filled in from catalog card ", h("b", {}, it.source.replace(/^catalog:/, "")), " — review and change anything. You can select several values.")) :
        h("div", { class: "msg warn" }, "No catalog card yet. Fill in the form, search the catalog, or let Claude read the card."),
      sug.notes ? h("div", { class: "msg info" }, "Claude notes: " + sug.notes) : null,
      (info.loss_hint || it.tone === "gentle") ? h("div", { class: "msg warn" }, "Loss / memorial poem: gentle tone is selected.") : null,
      chipRow("From", multi("from", ctx.relations, 4)),
      chipRow("To", multi("to", ctx.relations, 4)),
      chipRow("Event", multi("event", ctx.events, 4)),
      chipRow("Age group", multi("age_group", ctx.age_groups)),
      h("div", { class: "fields2", style: { marginTop: "6px" } },
        field("Recipient gender", h("select", { id: "in-gender", disabled: !ed, onchange: (e) => save("gender", e.target.value) },
          ["female", "male"].map((o) => h("option", { value: o, selected: it.gender === o ? true : null }, o === "female" ? "Female" : "Male")))),
        field("Tone", seg("in-tone", [["joyful", "Joyful"], ["gentle", "Gentle"]], it.tone, (v) => save("tone", v), !ed)),
        h("div", { class: "span2" }, field("Giver name (optional)", inp("giver_name"))))),
    h("div", { class: "card" }, h("div", { class: "rule" }), cardTitle("Poem card"),
      h("div", { class: "fields2" }, field("Card headline", inp("card_headline", { class: "serif-input" })), field("Closing line", inp("signature"))),
      field("Card text (used for the copy and to check generated images)", h("textarea", { id: "in-card_text", rows: 7, disabled: !ed,
        value: it.card_text || "", oninput: (e) => save("card_text", e.target.value) })),
      field("Notes for the copywriter (optional)", h("textarea", { id: "in-notes", rows: 2, disabled: !ed,
        value: it.notes || "", oninput: (e) => save("notes", e.target.value) }))));
  body.append(h("div", { class: "cols-2-3" }, left, right));
}

/* ------------------------------------------------------------------ stage 2: facts */
function renderFacts(body) {
  const ctx = C(), ed = editableStage("facts");
  const drafting = (ctx.tasks || []).some((t) => t.kind === `facts:${ctx.style.folder}`);
  body.append(h("div", { class: "msg info" }, h("span", {}, "ⓘ"), h("span", {}, "Claude reads the product photos and infographics of this style and suggests the facts. ",
    "Edit them, then approve. Slide copy and captions may only use approved facts. Approving this stage approves both cards below.")));
  if (drafting) body.append(h("div", { class: "msg warn", id: "facts-drafting" }, h("span", { class: "spin" }), h("span", {}, "Claude is reading ",
    `${ctx.style.photos.length} product photos and suggesting facts… (about a minute)`)));
  const cols = h("div", { class: "cols", style: { marginTop: "14px" } });
  body.append(cols);
  for (const [style, title] of [[ctx.style.folder, ctx.style.name], ["_Common", "All styles: brand, quality, packaging"]]) {
    const card = h("div", { class: "card", id: `facts-${style}` }, h("div", { class: "muted" }, "Loading…"));
    cols.append(card);
    api("GET", `/api/facts/${enc(style)}`).then((f) => {
      card.innerHTML = "";
      const ta = h("textarea", { id: `facts-text-${style}`, rows: 20, value: f.text, disabled: !ed });
      const saveF = (approved) => guard(async () => {
        await api("PUT", `/api/facts/${enc(style)}`, { text: ta.value, approved });
        toast(approved ? "Facts approved" : "Facts saved", "ok");
        reloadJob(true);
      });
      card.append(h("div", { class: "rule" }), cardTitle(title,
          h("span", { class: "pill " + (f.approved ? "ok" : "warn") }, f.approved ? "Approved" : f.exists ? "Draft" : "Not written")),
        style !== "_Common" ? h("div", { class: "strip", style: { marginBottom: "12px" } }, ctx.style.photos.map((p) => thumb(p, "", p))) : null,
        ta,
        h("div", { class: "row", style: { marginTop: "12px" } },
          h("button", { class: "btn", id: `btn-draft-${style}`, disabled: !ed,
            onclick: () => runTask(`/api/facts/${enc(style)}/draft`, { sku: sku() }, () => reloadJob(true)) }, "✦ Suggest facts from photos"),
          h("span", { class: "grow" }),
          h("button", { class: "btn", disabled: !ed, onclick: () => saveF(false) }, "Save"),
          h("button", { class: "btn", disabled: !ed, onclick: () => saveF(true) }, "Save & approve")));
    }).catch((e) => { card.textContent = e.message; });
  }
}

/* ------------------------------------------------------------------ stage 3: plan */
function planPatch() {
  const p = state.planDraft;
  return { plan: { hooks: p.hooks, hook_choice: p.hook_choice, slides: p.slides, caption: p.caption, hashtags: p.hashtags,
    voice: p.voice || "", carousel_type: p.carousel_type || "" } };
}
const savePlan = (delay) => queueSave(planPatch(), delay);
async function savePlanNow() { queueSave(planPatch(), 0); await flushSave(); renderJob(); }

function renderPlan(body) {
  const job = J(), ctx = C(), ed = editableStage("plan");
  state.planDraft = JSON.parse(JSON.stringify(job.plan));
  const p = state.planDraft;
  const base = `/api/jobs/${enc(sku())}/plan`;
  const gen = (part) => runTask(`${base}/generate`, { part, voice: p.voice || "", carousel_type: p.carousel_type || "" }, () => reloadJob(true));
  const last = ctx.last_post;
  body.append(h("div", { class: "card" }, h("div", { class: "fields2", style: { gridTemplateColumns: "1fr 1.4fr 1.6fr", alignItems: "end" } },
    field("Speaker voice", h("select", { id: "plan-voice", disabled: !ed, onchange: (e) => { p.voice = e.target.value; savePlan(0); } },
      h("option", { value: "" }, "Auto (rotate)"), Object.keys(ctx.voices).map((v) => h("option", { value: v, selected: p.voice === v ? true : null }, v[0].toUpperCase() + v.slice(1))))),
    field("Carousel type", h("select", { id: "plan-type", disabled: !ed, onchange: (e) => { p.carousel_type = e.target.value; savePlan(0); } },
      h("option", { value: "" }, "Auto"), Object.entries(ctx.carousel_types).map(([k, v]) => h("option", { value: k, selected: p.carousel_type === k ? true : null }, v)))),
    h("div", { class: "row", style: { justifyContent: "flex-end", paddingBottom: "2px" } },
      h("button", { class: "btn", id: "btn-baseline", disabled: !ed, onclick: async () => {
        if (p.slides.length && !(await confirmBox("Use baseline", "Replace the current slides with the 7-slide baseline?", "Replace"))) return;
        const d = await guard(() => api("POST", `${base}/baseline`)); if (d) { state.data = d; renderJob(); }
      } }, "Baseline (no Claude)"),
      h("button", { class: "btn primary", id: "btn-gen-plan", disabled: !ed, onclick: async () => {
        if (p.slides.length && !(await confirmBox("Generate plan", "Replace the current plan (texts, prompts, hooks, caption, hashtags)?", "Replace"))) return;
        gen("all");
      } }, "✦ Generate plan with Claude"))),
    h("div", { class: "row", style: { marginTop: "10px" } },
      last ? h("span", { class: "muted small grow" }, `Previous carousel: ${last.sku} — ${last.voice || "?"} voice, ${last.carousel_type || "?"}`) : h("span", { class: "grow" }),
      h("span", { class: "muted small" }, "Regenerate:"),
      ["hooks", "caption", "hashtags"].map((x) => h("button", { class: "btn link small", disabled: !ed || !p.slides.length, onclick: () => gen(x) }, x)))));
  if (!p.slides.length) {
    body.append(h("div", { class: "card" }, h("p", { class: "muted" }, "No plan yet. Generate one with Claude, or start from the baseline and write the copy yourself.")));
    return;
  }
  if (!p.slides.some((s) => s.n === state.sel)) state.sel = p.slides[0].n;

  // hooks
  const hooks = h("div", { class: "hooks" });
  p.hooks.forEach((hk, i) => {
    const ta = h("textarea", { id: `hook-${i}`, rows: 3, value: hk, disabled: !ed, oninput: (e) => {
      p.hooks[i] = e.target.value;
      if (p.hook_choice === i) { p.slides[0].headline = e.target.value; const hl = $("#sl-1-headline"); if (hl) hl.value = e.target.value; }
      savePlan();
    } });
    hooks.append(h("div", { class: "hookcard" + (p.hook_choice === i ? " sel" : ""), id: `hook-card-${i}`, onclick: (e) => {
      if (!ed || p.hook_choice === i) return;
      p.hook_choice = i; p.slides[0].headline = p.hooks[i];
      document.querySelectorAll(".hookcard").forEach((c, j) => c.classList.toggle("sel", j === i));
      const hl = $("#sl-1-headline"); if (hl) hl.value = p.hooks[i];
      savePlan(0);
    } }, h("div", { class: "hk-top" }, h("span", { class: "eyebrow-label" }, `Option ${"ABC"[i]}`), h("span", { class: "radio", id: `hook-r-${i}` })), ta));
  });
  body.append(h("div", { class: "card" }, h("div", { class: "rule" }), cardTitle("Hook — choose one, edit freely"), hooks, h("div", { id: "hook-check" })));

  // storyboard + inspector
  const add = h("div", { class: "sb add", id: "btn-add-slide", onclick: () => {
    if (!ed) return;
    if (p.slides.length >= 10) { toast("A carousel has at most 10 slides.", "error"); return; }
    p.slides.push({ n: null, purpose: "New slide", layout: "statement", source: "none", slot: null, prompt: "",
      references: [], headline: "", subtext: "", items: [], button: "", eyebrow: "", quote: "", note: "", script: "",
      text_pos: "top", shade: 0.55 });
    state.sel = p.slides.length;
    savePlanNow();
  } }, "+ Add slide");
  body.append(h("div", { class: "card" }, h("div", { class: "rule" }),
    cardTitle(`Storyboard · ${p.slides.length} slides`, h("span", { class: "muted small" }, "7–10 slides · click a slide to edit it")),
    storyboard("plan", { add }), slideInspector(p, ed)));

  // caption, hashtags & brand spec
  body.append(h("div", { class: "cols-3-2", style: { marginTop: "18px" } },
    h("div", { class: "card" }, h("div", { class: "rule" }), cardTitle("Caption & hashtags"),
      field("Caption", h("textarea", { id: "plan-caption", rows: 10, value: p.caption, disabled: !ed,
        oninput: (e) => { p.caption = e.target.value; savePlan(); } })),
      field("Hashtags · #bewished #bewishedgifts #morethanjewelry are always added last", h("textarea", { id: "plan-hashtags", rows: 3, value: p.hashtags.join(" "), disabled: !ed,
        oninput: (e) => { p.hashtags = e.target.value.split(/[\s,;]+/).filter(Boolean); savePlan(); } })),
      h("div", { id: "tag-check" })),
    h("div", { class: "card" }, h("div", { class: "rule" }), cardTitle("Brand spec check"), h("div", { id: "lint-check" }))));
  refreshChecks();
}

function slideInspector(p, ed) {
  const ctx = C();
  const i = p.slides.findIndex((s) => s.n === state.sel);
  const s = p.slides[i];
  const set = (k, v, now) => { s[k] = v; now ? savePlanNow() : savePlan(); };
  const inp = (k, attrs) => h("input", Object.assign({ type: "text", id: `sl-${i + 1}-${k}`, value: s[k] || "", disabled: !ed,
    oninput: (e) => set(k, e.target.value) }, attrs || {}));
  const ta = (k, rows, attrs) => h("textarea", Object.assign({ id: `sl-${i + 1}-${k}`, rows, value: s[k] || "", disabled: !ed,
    oninput: (e) => set(k, e.target.value) }, attrs || {}));
  const sel = (k, opts, now) => h("select", { id: `sl-${i + 1}-${k}`, disabled: !ed, onchange: (e) => set(k, e.target.value || null, now) },
    opts.map((o) => h("option", { value: o, selected: (s[k] || "") === o ? true : null }, o || "(none)")));
  const move = (d) => { const j = i + d; if (j < 0 || j >= p.slides.length) return; [p.slides[i], p.slides[j]] = [p.slides[j], p.slides[i]]; state.sel = j + 1; savePlanNow(); };
  const refs = referenceStrip(s, ed);
  const needsImage = ["generate", "library", "common"].includes(s.source);
  return h("div", { class: "inspector", id: `slide-card-${i + 1}`, style: { marginTop: "16px" } },
    h("div", {}, previewEl(s.n, 360), slideNav(),
      h("div", { class: "row", style: { marginTop: "10px", justifyContent: "center" } },
        h("button", { class: "btn small", disabled: !ed || i === 0, onclick: () => move(-1) }, "Move left"),
        h("button", { class: "btn small", disabled: !ed || i === p.slides.length - 1, onclick: () => move(1) }, "Move right"),
        h("button", { class: "btn small danger", disabled: !ed || p.slides.length <= 7, onclick: async () => {
          if (await confirmBox("Delete slide", `Delete slide ${i + 1}?`, "Delete", true)) { p.slides.splice(i, 1); state.sel = Math.max(1, i); savePlanNow(); }
        } }, "Delete"))),
    h("div", {},
      h("div", { class: "row" }, h("span", { style: { font: "700 22px var(--serif)", color: "var(--gold)" } }, pad(i + 1)), inp("purpose", { style: { maxWidth: "380px" } })),
      kindToggle(s, ed),
      h("div", { class: "fields2" },
        field("Layout", sel("layout", ctx.layouts, true)),
        field("Image source", sel("source", ctx.sources, true)),
        h("div", { class: "span2" }, field("Headline · *word* = gold", inp("headline", { class: "serif-input" }))),
        h("div", { class: "span2" }, field("Subtext · new line = line break", ta("subtext", 3)))),
      h("details", { class: "more", open: (s.eyebrow || s.quote || s.note || s.script || (s.items || []).length || s.button) ? true : null },
        h("summary", {}, "More fields: eyebrow · quote · note · script · list · button · library slot"),
        h("div", { class: "fields2" },
          field("Eyebrow label", inp("eyebrow")), field("Small grey note", inp("note")),
          h("div", { class: "span2" }, field("Quote (italic, gold bar)", inp("quote"))),
          field("Script overlay (handwriting)", inp("script", { disabled: !ed || s.source === "none" })),
          field("Library slot", sel("slot", ["", "options", "quality", "cta"])),
          field("List items (one per line)", h("textarea", { id: `sl-${i + 1}-items`, rows: 3, value: (s.items || []).join("\n"), disabled: !ed,
            oninput: (e) => set("items", e.target.value.split("\n").filter((x) => x.trim())) })),
          field("Button text", inp("button")))),
      needsImage ? h("div", {},
        field("ChatGPT image prompt", ta("prompt", 4)),
        h("details", {}, h("summary", { class: "muted small", style: { cursor: "pointer", margin: "6px 0" } }, "Rules added to every prompt automatically"), h("div", { class: "suffix" }, ctx.suffix)),
        h("label", { class: "f" }, "Reference images (uploaded to ChatGPT)"), refs) : null));
}

/* black slide <-> slide with an image: Plan stage, and on the Images stage after the plan is approved */
function kindToggle(s, ed) {
  const black = s.source === "none";
  return h("div", { class: "kind-toggle", id: `kind-${s.n}` },
    seg(`kind-seg-${s.n}`, [["black", "Black slide"], ["image", "Slide with image"]], black ? "black" : "image",
      (v) => setSlideKind(s.n, v === "black"), !ed),
    h("span", { class: "muted small" }, black ? "Text on the brand black, no image needed." : "Text over a photo generated or chosen for this slide."));
}
async function setSlideKind(n, black) {
  await flushSave();
  const d = await guard(() => api("POST", `/api/jobs/${enc(sku())}/slides/${n}/kind`, { black }));
  if (d) { state.data = d; state.bust = Date.now(); renderJob(); }
}

/* reference images: thumbnails with remove buttons + "Choose…" that opens the picker */
function referenceStrip(s, ed) {
  const save = (list) => saveReferences(s.n, list);
  return h("div", { class: "row", style: { alignItems: "flex-start" } },
    h("div", { class: "refs", id: `refs-${s.n}` }, (s.references || []).map((r, ri) => h("div", { class: "ref" }, thumb(r, "", r),
      ed ? h("button", { class: "x", title: "Remove", onclick: () => save(s.references.filter((_, j) => j !== ri)) }, "×") : null))),
    ed ? h("button", { class: "btn small", id: `btn-refs-${s.n}`, onclick: () => pickReferences(s) }, "+ Choose references…") : null);
}
async function saveReferences(n, list) {
  await flushSave();
  const d = await guard(() => api("PUT", `/api/jobs/${enc(sku())}/slides/${n}/references`, { references: list }));
  if (d) { state.data = d; renderJob(); }
}
const SEEN_KEY = "refs-seen";
function seenRefs() { try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]")); } catch (e) { return new Set(); } }
async function pickReferences(s) {
  const chosen = (s.references || []).slice();
  const seen = seenRefs(), firstTime = !seen.size;
  const box = h("div", { class: "picker", id: "ref-picker" });
  let groups = [];
  const draw = () => {
    box.innerHTML = "";
    const styleGroup = groups.find((g) => g.key === "style");
    box.append(h("div", { class: "row" },
      h("span", { class: "muted small grow" }, "Click photos to add or remove them; the number is the upload order. Added photos to a folder? Click Refresh."),
      h("button", { class: "btn small", id: "btn-refs-refresh", onclick: load }, "↻ Refresh"),
      styleGroup ? h("button", { class: "btn small", onclick: () => guard(() => api("POST", "/api/open", { path: styleGroup.folder })) }, "Open style folder") : null));
    for (const g of groups) {
      if (!g.files.length && g.key !== "style") continue;
      const grid = h("div", { class: "picker-grid" }, g.files.map((f) => {
        const i = chosen.indexOf(f);
        return h("div", { class: "pick" + (i >= 0 ? " on" : "") + (!firstTime && !seen.has(f) ? " new" : ""), title: f, "data-file": f,
          onclick: () => { const j = chosen.indexOf(f); if (j >= 0) chosen.splice(j, 1); else chosen.push(f); draw(); } },
          h("img", { src: `/thumb?path=${enc(f)}`, loading: "lazy", alt: f }), h("span", { class: "ord" }, i + 1), h("span", { class: "nm" }, f.split("/").pop()));
      }));
      box.append(g.key === "other"
        ? h("details", { class: "picker-group", open: g.files.some((f) => chosen.includes(f)) ? true : null },
          h("summary", { class: "eyebrow-label", style: { cursor: "pointer" } }, `${g.title} · ${g.files.length}`), grid)
        : h("div", { class: "picker-group" }, h("span", { class: "eyebrow-label" }, `${g.title} · ${g.files.length}`),
          g.files.length ? grid : h("div", { class: "muted small" }, `No photos in ${g.folder} yet.`)));
    }
  };
  async function load() {
    const d = await guard(() => api("GET", `/api/jobs/${enc(sku())}/references`));
    if (!d) return;
    groups = d.groups;
    draw();
  }
  await load();
  const ok = await modal(`References for slide ${pad(s.n)}`, box,
    [{ label: "Cancel", value: false }, { label: "Use these references", value: true, cls: "primary", id: "modal-ok" }], "wide");
  try { localStorage.setItem(SEEN_KEY, JSON.stringify(groups.flatMap((g) => g.files))); } catch (e) { /* storage blocked */ }
  if (ok) await saveReferences(s.n, chosen);
}

function refreshChecks() {
  const ctx = C();
  if (!ctx) return;
  const tc = $("#tag-check");
  if (tc) {
    const c = ctx.hashtag_check;
    tc.innerHTML = "";
    tc.append(h("div", { class: "row small", style: { marginTop: "8px" } }, h("span", { class: "badge " + (c.errors.length ? "err" : "ok") }, `${c.count} hashtags`),
      c.closest ? h("span", { class: "muted" }, `closest previous set: ${c.closest.sku} (${Math.round(c.closest.overlap * 100)}% overlap)`) : h("span", { class: "muted" }, "no previous sets yet")));
    c.errors.forEach((e) => tc.append(h("div", { class: "msg err" }, e)));
    c.warnings.forEach((e) => tc.append(h("div", { class: "msg warn" }, e)));
  }
  const lc = $("#lint-check");
  if (lc && ctx.lint) {
    lc.innerHTML = "";
    const job = J(), n = (job.plan.slides || []).length;
    const errs = ctx.lint.errors.join(" ");
    lc.append(
      /emoji/i.test(errs) ? statusRow("err", "Emoji on slides", ctx.lint.errors.find((e) => /emoji/i.test(e))) : statusRow("ok", "No emoji on slides"),
      /7 to 10/.test(errs) ? statusRow("err", `${n} slides`, "A carousel has 7 to 10 slides.") : statusRow("ok", `${n} slides`, "Within 7–10"),
      ctx.hashtag_check.errors.length ? statusRow("err", "Hashtags", ctx.hashtag_check.errors.join(" ")) :
        statusRow("ok", `${ctx.hashtag_check.count} hashtags`, "Brand tags last · set not used before"),
      ctx.lint.warnings.map((w) => statusRow("warn", "Please check", w)),
      ctx.hook_used ? statusRow("warn", "Hook used before", `${ctx.hook_used.sku} (${ctx.hook_used.date})`) : null);
  }
  const hc = $("#hook-check");
  if (hc) { hc.innerHTML = ""; if (ctx.hook_used) hc.append(h("div", { class: "msg warn" }, `This hook was already used for ${ctx.hook_used.sku} (${ctx.hook_used.date}).`)); }
}

/* ------------------------------------------------------------------ stage 4: images */
function renderImages(body) {
  const job = J(), ctx = C(), ed = editableStage("images");
  const base = `/api/jobs/${enc(sku())}/images`;
  body.append(h("div", { class: "card" }, h("div", { class: "row" },
    h("div", { class: "grow" }, h("div", { class: "rule" }), h("h3", { style: { margin: 0 } }, "Images"),
      h("div", { class: "muted small" }, `Generator: ${ctx.backend === "claude_chrome" ? "ChatGPT via Claude in Chrome" : ctx.backend}. Manual: Copy prompt → ChatGPT → download → Import latest download.`)),
    h("button", { class: "btn", onclick: () => window.open(ctx.chatgpt_url, "_blank") }, "Open ChatGPT"),
    job.chat_url ? h("a", { href: job.chat_url, target: "_blank", class: "small" }, "This carousel's ChatGPT chat") : null,
    h("button", { class: "btn primary", id: "btn-gen-missing", disabled: !ed, onclick: () => runTask(`${base}/generate-missing`, {}, () => reloadJob(true)) },
      "✦ Generate all missing")),
    h("div", { style: { marginTop: "14px" } }, storyboard("images"))));
  const s = selectedSlide();
  if (s) body.append(imagePanel(s, ed, base));
}

function imagePanel(s, ed, base) {
  const job = J(), ctx = C(), n = s.n;
  const entry = job.images[String(n)] || { versions: [], current: 0 };
  const cur = entry.versions[entry.current];
  const url = `${base}/${n}`;
  const after = () => reloadJob(true);
  const post = (path, b) => guard(async () => { state.data = await api("POST", `${url}/${path}`, b || {}); state.bust = Date.now(); renderJob(); });
  if (s.source === "none") return h("div", { class: "card", id: `imgrow-${n}`, style: { marginTop: "18px" } },
    cardTitle(`Slide ${pad(n)} · ${s.purpose}`, h("span", { class: "pill plain" }, s.layout)),
    h("div", { class: "row", style: { alignItems: "flex-start", gap: "24px" } }, previewEl(n, 260),
      h("div", {}, kindToggle(s, ed), slideNav())));
  const fileIn = h("input", { type: "file", accept: "image/*", class: "hidden", id: `upload-${n}`, onchange: async (e) => {
    const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append("file", f); await post("upload", fd);
  } });
  let libChoices = [];
  if (s.source === "library" && s.slot && ctx.library[s.slot]) libChoices = ctx.library[s.slot].filter((v) => v.approved).map((v) => ({ ...v, kind: "library" }));
  if (s.source === "common") libChoices = ctx.library.cta.filter((v) => v.approved).map((v) => ({ ...v, kind: "library" }))
    .concat(ctx.common_photos.map((f) => ({ file: f, kind: "common" })));
  const qa = cur && cur.qa;
  return h("div", { class: "card", id: `imgrow-${n}`, style: { marginTop: "18px" } },
    cardTitle(`Slide ${pad(n)} · ${s.purpose}`, h("span", { class: "pill gold" }, s.source + (s.slot ? ` · ${s.slot}` : "")),
      cur ? h("span", { class: "pill plain" }, cur.origin) : null),
    h("div", { class: "inspector", style: { gridTemplateColumns: "300px 1fr 250px" } },
      h("div", { class: "main" }, cur ? h("img", { class: "thumb", src: fileUrl(cur.file), style: { width: "300px", height: "375px" },
        onclick: () => lightbox(fileUrl(cur.file), `Slide ${n}`) }) : h("div", { class: "empty", style: { width: "300px", height: "375px" } }, "No image yet"),
        entry.versions.length > 1 ? h("div", {}, h("label", { class: "f" }, `Versions (${entry.versions.length})`),
          h("div", { class: "versions" }, entry.versions.map((v, i) => h("div", { class: "version" + (i === entry.current ? " cur" : ""),
            title: `Version ${i + 1} (${v.origin})`, onclick: () => { if (!ed || i === entry.current) return; queueSave({ images_current: { [n]: i } }, 0); setTimeout(after, 300); } },
            h("img", { src: fileUrl(v.file) }), h("span", { class: "vtag" }, i === entry.current ? "✓ Selected" : `v${i + 1}`))))) : null,
        slideNav()),
      h("div", {},
        qa ? h("div", { class: "msg " + (qa.ok ? "ok" : "warn") }, qa.ok ? "QA: OK" : "QA issues: " + qa.issues.join("; ")) : null,
        libChoices.length ? h("div", {}, h("label", { class: "f" }, s.source === "common" ? "Choose a common image" : `Choose from library (${s.slot})`),
          h("div", { class: "libpick" }, libChoices.map((v) => h("img", { src: fileUrl(v.file), title: v.file, onclick: () => { if (!ed) return;
            post("use", v.kind === "library" ? { kind: "library", style: v.style, slot: v.slot, variant: v.variant } : { kind: "common", file: v.file }); } })))) : null,
        s.source === "library" && !libChoices.length ? h("div", { class: "msg info" }, `The ${s.slot} library for this style is empty: generate an image, then "Save to library".`) : null,
        s.prompt ? h("div", {}, h("label", { class: "f" }, "Prompt"), h("div", { class: "prompt-box" }, s.prompt)) : null,
        ["generate", "library"].includes(s.source) ? h("div", {}, h("label", { class: "f" }, "References (uploaded to ChatGPT)"), referenceStrip(s, ed)) : null,
        h("label", { class: "f" }, "Live preview with text"), previewEl(n, 200)),
      h("div", { class: "actions-col" },
        h("button", { class: "btn primary", id: `gen-${n}`, disabled: !ed, onclick: () => runTask(`${url}/generate`, {}, after) }, "✦ Generate (ChatGPT)"),
        h("button", { class: "btn", disabled: !ed || !cur, id: `qa-${n}`, onclick: () => runTask(`${url}/qa`, {}, after) }, "✦ QA check"),
        h("button", { class: "btn", onclick: () => { navigator.clipboard.writeText(s.prompt + "\n\n" + ctx.suffix).then(() => toast("Prompt copied")); } }, "Copy prompt"),
        (s.references || []).length ? h("button", { class: "btn", onclick: () => guard(() => api("POST", "/api/open", { path: s.references[0] })) }, "Show references") : null,
        h("button", { class: "btn", id: `import-${n}`, disabled: !ed, onclick: () => post("import") }, "Import latest download"),
        h("button", { class: "btn", disabled: !ed, onclick: () => fileIn.click() }, "Upload file…"), fileIn,
        h("button", { class: "btn", disabled: !ed, onclick: () => post("use", { kind: "input" }) }, "Use input photo"),
        h("button", { class: "btn", id: `black-${n}`, disabled: !ed, onclick: () => setSlideKind(n, true) }, "Make it a black slide"),
        cur && ["options", "quality", "cta"].includes(s.slot) && cur.origin !== "library" ? h("button", { class: "btn", id: `lib-${n}`, disabled: !ed, onclick: async () => {
          if (await confirmBox("Save to style library", `Approve this image as a reusable '${s.slot}' image for ${s.slot === "cta" ? "all styles" : C().style.name}?`, "Approve & save"))
            post("library", { slot: s.slot });
        } }, "Save to library") : null)));
}

/* ------------------------------------------------------------------ stage 5: slides */
function renderSlides(body) {
  const job = J(), ed = editableStage("slides");
  const render = (only) => runTask(`/api/jobs/${enc(sku())}/render`, only ? { only } : {}, () => reloadJob(true));
  body.append(h("div", { class: "card" }, h("div", { class: "row" },
    h("div", { class: "grow" }, h("div", { class: "rule" }), h("h3", { style: { margin: 0 } }, "Slides"),
      h("div", { class: "muted small" }, job.render.rendered_at ? `Last render ${job.render.rendered_at.replace("T", " ")} · text is drawn by the app, never by the image model` : "Not rendered yet")),
    h("button", { class: "btn primary", id: "btn-render", disabled: !ed, onclick: async () => { await flushSave(); render(); } }, "Render all slides")),
    h("div", { style: { marginTop: "14px" } }, storyboard("slides"))));
  const s = selectedSlide();
  if (!s) return;
  const n = s.n, f = (job.render.files || {})[String(n)];
  const dirty = !f || (job.render.dirty || {})[String(n)];
  const save = (k, v) => {
    s[k] = v;
    queueSave({ slide_text: { [n]: { [k]: v } } });
    const b = $("#slide-status"); if (b) { b.className = "pill warn"; b.textContent = "Needs render"; }
    const t = document.querySelector(`#sb-${n} .st`); if (t) t.className = "st warn";
  };
  const inp = (k) => h("input", { type: "text", id: `st-${n}-${k}`, value: s[k] || "", disabled: !ed, oninput: (e) => save(k, e.target.value) });
  const extra = ["eyebrow", "quote", "note", "script"].filter((k) => s[k] || (["guide", "statement"].includes(s.layout) && k !== "script"));
  body.append(h("div", { class: "card", id: `slidebox-${n}`, style: { marginTop: "18px" } },
    cardTitle(`Slide ${pad(n)} · ${s.purpose}`, h("span", { class: "pill plain" }, s.layout),
      h("span", { class: "pill " + (dirty ? "warn" : "ok"), id: "slide-status" }, dirty ? "Needs render" : "Up to date")),
    h("div", { class: "inspector", style: { gridTemplateColumns: "400px 1fr" } },
      h("div", {}, f ? h("div", { class: "preview", style: { width: "400px", height: "500px" } }, h("img", { src: fileUrl(f), class: "thumb",
        onclick: () => lightbox(fileUrl(f), `Slide ${n}`) })) : h("div", { class: "empty", style: { width: "400px", height: "500px" } }, "Not rendered yet"),
        slideNav()),
      h("div", {},
        field("Headline · *word* = gold", h("textarea", { id: `st-${n}-headline`, rows: 2, class: "serif-input", value: s.headline || "", disabled: !ed,
          oninput: (e) => save("headline", e.target.value) })),
        field("Subtext", h("textarea", { rows: 3, id: `st-${n}-subtext`, value: s.subtext || "", disabled: !ed, oninput: (e) => save("subtext", e.target.value) })),
        s.layout === "list" ? field("Items (one per line)", h("textarea", { rows: 3, value: (s.items || []).join("\n"), disabled: !ed,
          oninput: (e) => save("items", e.target.value.split("\n").filter((x) => x.trim())) })) : null,
        s.layout === "cta" ? field("Button", inp("button")) : null,
        h("div", { class: "fields2" }, extra.map((k) => field(k[0].toUpperCase() + k.slice(1), inp(k)))),
        h("div", { class: "fields2" },
          field("Text position", seg(`st-${n}-pos`, [["top", "Top"], ["bottom", "Bottom"]], s.text_pos || "top", (v) => save("text_pos", v), !ed)),
          field("Image position", seg(`st-${n}-img`, [["top", "Top"], ["center", "Center"], ["bottom", "Bottom"]], s.img_pos || "center", (v) => save("img_pos", v), !ed)),
          field(`Shade (darkness behind text)`, h("input", { type: "range", min: 0, max: 1, step: 0.05, value: s.shade ?? 0.55, disabled: !ed, style: { width: "100%", accentColor: "#E2C98A" },
            onchange: (e) => save("shade", parseFloat(e.target.value)) })),
          s.layout === "cta" ? field("Logo", h("label", { class: "check" }, h("input", { type: "checkbox", checked: !!s.logo, disabled: !ed, onchange: (e) => save("logo", e.target.checked) }), "Show logo")) : h("div")),
        h("div", { class: "row", style: { marginTop: "16px" } }, h("span", { class: "grow" }),
          h("button", { class: "btn", id: `rerender-${n}`, disabled: !ed || !f, onclick: async () => { await flushSave(); render([n]); } }, "Re-render this slide"))))));
}

/* ------------------------------------------------------------------ stage 6: final */
function renderFinal(body) {
  const job = J(), ed = editableStage("final");
  const files = job.render.files || {};
  const slug = ([].concat(job.intake.event || [])[0] || "carousel").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "carousel";
  const today = new Date(); const d = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  const copy = (id, label) => h("button", { class: "btn small", onclick: () => navigator.clipboard.writeText($(id).value).then(() => toast(`${label} copied`)) }, `Copy ${label.toLowerCase()}`);
  const left = h("div", { class: "card" }, h("div", { class: "rule" }), cardTitle(`Final carousel · ${job.plan.slides.length} slides`, h("span", { class: "pill ok" }, "Ready to save")),
    h("div", { class: "finalgrid" }, job.plan.slides.map((s) => h("figure", {}, thumb(files[String(s.n)], "", `Slide ${s.n}`),
      h("figcaption", {}, `${pad(s.n)} · ${s.purpose}`)))));
  const right = h("div", {},
    h("div", { class: "card" }, cardTitle("Instagram caption", copy("#final-caption", "Caption")),
      h("textarea", { id: "final-caption", rows: 10, value: job.plan.caption, disabled: !ed,
        oninput: (e) => queueSave({ final_text: { caption: e.target.value } }) })),
    h("div", { class: "card" }, cardTitle("Hashtags", copy("#final-hashtags", "Hashtags")),
      h("textarea", { id: "final-hashtags", rows: 4, value: job.plan.hashtags.join(" "), disabled: !ed,
        oninput: (e) => queueSave({ final_text: { hashtags: e.target.value } }) }), h("div", { id: "tag-check" })),
    h("div", { class: "card" }, cardTitle("Pre-publish check"), h("div", { id: "lint-check" })),
    h("div", { class: "card" }, cardTitle("Save"),
      h("table", { class: "kv" },
        h("tr", {}, h("td", {}, "Destination"), h("td", {}, `Carousels/${d}_${job.sku}_${slug}/`)),
        h("tr", {}, h("td", {}, "Files"), h("td", {}, `bewished_slide_1..${job.plan.slides.length}.png · caption & hashtags · plan.md · raw/`)),
        h("tr", {}, h("td", {}, "Then deletes"), h("td", {}, h("b", {}, job.input_file), " and the work folder"))),
      h("button", { class: "btn primary", id: "btn-finalize", disabled: !ed, style: { width: "100%", justifyContent: "center", marginTop: "14px", padding: "13px" },
        onclick: finalizeJob }, "Approve & Save carousel")));
  body.append(h("div", { class: "cols-3-2" }, left, right));
  refreshChecks();
}
async function finalizeJob() {
  if (!(await flushSave())) return;
  if (!(await confirmBox("Approve & Save", `Save the final carousel and DELETE the input photo ${J().input_file}?\nThis cannot be undone.`, "Approve & Save"))) return;
  const res = await guard(() => api("POST", `/api/jobs/${enc(sku())}/finalize`));
  if (!res) return;
  (res.warnings || []).forEach((w) => toast(w, "error"));
  await refreshSideJobs();
  state.view = "done";
  plainTopbar("Carousel saved");
  const v = $("#view");
  v.innerHTML = "";
  v.append(h("div", { class: "page" }, h("div", { class: "card", id: "done-panel" }, h("div", { class: "rule" }), h("h2", {}, "✓ Carousel saved"),
    h("p", {}, "Saved to ", h("b", {}, res.dest)),
    h("div", { class: "row" },
      h("button", { class: "btn", onclick: () => guard(() => api("POST", "/api/open", { path: res.dest })) }, "Open folder"),
      h("button", { class: "btn primary", id: "btn-next", onclick: () => go("queue") }, "Next in queue →")))));
}

/* ------------------------------------------------------------------ library, settings, system */
async function showLibrary() {
  plainTopbar("Style library");
  const d = await guard(() => api("GET", "/api/library"));
  const v = $("#view"); v.innerHTML = "";
  const page = h("div", { class: "page" });
  v.append(page);
  page.append(h("div", { class: "rule" }), h("h2", {}, "Reusable images per style"),
    h("p", { class: "muted" }, "Approved images are offered (least recently used first) on library slides. Generated images join the library with 'Save to library' on the Images stage."));
  if (!d || !d.styles.length) { page.append(h("div", { class: "card" }, "The library is empty.")); return; }
  const set = (b) => guard(async () => { await api("POST", "/api/library", b); showLibrary(); });
  for (const st of d.styles) {
    const p = h("div", { class: "card" }, cardTitle(st.style === "_Common" ? "All styles (_Common)" : st.style));
    for (const [slot, items] of Object.entries(st.slots)) {
      p.append(h("div", { class: "eyebrow-label" }, slot), h("div", { class: "libslot" }, items.map((it) => h("div", { class: "libitem" },
        thumb(it.file, "", it.file),
        h("div", { class: "row small", style: { marginTop: "6px" } }, h("span", { class: "badge " + (it.approved ? "ok" : "warn") }, it.approved ? "approved" : "not approved"),
          h("span", { class: "muted" }, `${it.uses} uses`)),
        h("div", { class: "row", style: { marginTop: "6px" } },
          h("button", { class: "btn small", onclick: () => set({ style: st.style, slot, variant: it.variant, approved: !it.approved }) }, it.approved ? "Unapprove" : "Approve"),
          h("button", { class: "btn small danger", onclick: async () => { if (await confirmBox("Remove image", `Remove ${it.variant} from the library?`, "Remove", true))
            set({ style: st.style, slot, variant: it.variant, remove: true }); } }, "Remove"))))));
    }
    page.append(p);
  }
}

const SETTING_HELP = {
  claude_cmd: "Claude Code command", model: "Claude model for card reading, facts, plan and QA (sonnet, opus…)",
  image_backend: "claude_chrome = automatic ChatGPT via Claude in Chrome", downloads_dir: "Where Chrome saves downloads",
  catalog_dir: "Poem-card catalog folder (card images + PoemText files)",
  chatgpt_url: "ChatGPT address", text_timeout: "Claude timeout (seconds)", image_timeout: "Image generation timeout (seconds)",
  qa_enabled: "Check every generated image with Claude", max_auto_retries: "Automatic regenerations when QA fails",
  overlap_threshold: "Warn when a hashtag set overlaps a previous one by more than this (0-1)",
  image_style_suffix: "Rules appended to every image prompt", bell_sound: "Play a soft bell when all missing images are generated", port: "Local port (restart needed)",
};
async function showSettings() {
  plainTopbar("Settings");
  const s = await guard(() => api("GET", "/api/settings"));
  const v = $("#view"); v.innerHTML = "";
  if (!s) return;
  const form = h("div", { class: "card" });
  const vals = {};
  for (const [k, val] of Object.entries(s)) {
    let input;
    if (typeof val === "boolean") input = h("label", { class: "check" }, h("input", { type: "checkbox", checked: val, onchange: (e) => (vals[k] = e.target.checked) }), "enabled");
    else if (k === "image_style_suffix") input = h("textarea", { rows: 7, value: val, oninput: (e) => (vals[k] = e.target.value) });
    else if (k === "image_backend") input = h("select", { onchange: (e) => (vals[k] = e.target.value) }, ["claude_chrome"].map((o) => h("option", { value: o, selected: val === o ? true : null }, o)));
    else input = h("input", { type: typeof val === "number" ? "number" : "text", step: "any", value: String(val), oninput: (e) => (vals[k] = e.target.value) });
    form.append(field(`${k} — ${SETTING_HELP[k] || ""}`, input));
  }
  form.append(h("div", { class: "row", style: { marginTop: "16px" } }, h("span", { class: "grow" }),
    h("button", { class: "btn", id: "btn-test-bell", onclick: bell }, "♪ Test bell"),
    h("button", { class: "btn primary", id: "btn-save-settings", onclick: () => guard(async () => { state.settings = await api("PUT", "/api/settings", vals); toast("Settings saved", "ok"); showSettings(); }) }, "Save settings")));
  v.append(h("div", { class: "page" }, h("div", { class: "rule" }), h("h2", {}, "Settings"), form));
}

async function showSystem() {
  plainTopbar("System check");
  const v = $("#view"); v.innerHTML = "";
  const page = h("div", { class: "page" }, h("div", { class: "rule" }), h("h2", {}, "System check"), h("div", { class: "muted" }, "Checking…"));
  v.append(page);
  const s = await guard(() => api("GET", "/api/system"));
  if (!s) return;
  page.innerHTML = "";
  const ok = (b) => h("span", { class: "pill " + (b ? "ok" : "err") }, b ? "OK" : "missing");
  page.append(h("div", { class: "rule" }), h("h2", {}, "System check"),
    h("div", { class: "card" }, h("table", { class: "kv" },
      h("tr", {}, h("td", {}, "Python"), h("td", {}, s.python)),
      h("tr", {}, h("td", {}, "Browser for rendering"), h("td", {}, ok(!!s.browser), " ", s.browser)),
      h("tr", {}, h("td", {}, "Claude Code CLI"), h("td", {}, ok(!!s.claude), " ", s.claude, " ", s.claude_version)),
      h("tr", {}, h("td", {}, "Downloads folder"), h("td", {}, ok(s.downloads.exists), " ", s.downloads.path)),
      h("tr", {}, h("td", {}, "Image generator"), h("td", {}, s.image_backend)),
      Object.entries(s.folders).map(([k, b]) => h("tr", {}, h("td", {}, `Folder: ${k}`), h("td", {}, ok(b)))))),
    h("div", { class: "card" }, cardTitle("Style folders (RealProductPhotos)"), h("table", { class: "kv" },
      s.styles.map((st) => h("tr", {}, h("td", {}, st.type), h("td", {},
        h("span", { class: "pill " + (st.status === "ready" ? "ok" : "warn") }, st.status === "ready" ? `${st.photos} photos` : st.status === "empty" ? "empty" : "no folder"),
        " ", h("span", { class: "muted small" }, st.folder)))))));
}

/* ------------------------------------------------------------------ init */
function init() {
  document.querySelectorAll(".nav[data-view]").forEach((b) => b.addEventListener("click", () => go(b.dataset.view)));
  $("#loghead").addEventListener("click", () => { $("#logdrawer").classList.toggle("collapsed"); $("#logtoggle").textContent = $("#logdrawer").classList.contains("collapsed") ? "▲" : "▼"; });
  $("#lightbox").addEventListener("click", () => $("#lightbox").classList.add("hidden"));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("#lightbox").classList.add("hidden"); } });
  document.addEventListener("pointerdown", unlockAudio);
  api("GET", "/api/settings").then((s) => { state.settings = s; }).catch(() => {});
  window.addEventListener("beforeunload", () => { if (Object.keys(pending).length) flushSave(); });
  api("GET", "/api/system").then((s) => { if (s.image_backend === "fake") $("#mode-note").textContent = "DEMO MODE: no Claude / ChatGPT calls"; }).catch(() => {});
  setInterval(pollLog, 1500);
  setInterval(pollTasks, 1000);
  pollLog();
  go("queue");
}
init();
