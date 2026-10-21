// Tempa single-page app: hash router + views. No build step.
const $app = document.getElementById("app");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (iso) => new Date(iso).toLocaleString(I18n.lang === "ms" ? "ms-MY" : "en-MY", { dateStyle: "medium", timeStyle: "short" });
const pct = (x) => Math.round((x || 0) * 100);

function toast(msg, kind = "info") {
  const el = document.getElementById("toast");
  el.textContent = msg; el.className = `show ${kind}`;
  clearTimeout(toast._t); toast._t = setTimeout(() => (el.className = ""), 3200);
}
function errMsg(e) { return STRINGS[I18n.lang][`err_${e.message}`] || STRINGS.en[`err_${e.message}`] || t("err_generic"); }

// ---------------------------------------------------------------- router
const routes = [
  [/^#\/login$/, viewLogin, false],
  [/^#\/t\/(\w+)$/, viewPublicTranscript, false],
  [/^#\/home$/, viewHome, true],
  [/^#\/course\/(\d+)$/, viewCourse, true],
  [/^#\/module\/(\d+)(?:\/(\d+))?$/, viewModule, true],
  [/^#\/squad\/(\d+)$/, viewSquad, true],
  [/^#\/bounty\/(\d+)$/, viewBounty, true],
  [/^#\/transcript$/, viewTranscript, true],
  [/^#\/dashboard\/(\d+)$/, viewDashboard, true],
];

let cleanup = null;
async function router() {
  if (cleanup) { cleanup(); cleanup = null; }
  const hash = location.hash || "#/home";
  const match = routes.find(([re]) => re.test(hash));
  if (!match) { location.hash = "#/home"; return; }
  const [re, view, needsAuth] = match;
  if (needsAuth && !Api.token) { location.hash = "#/login"; return; }
  renderNav();
  $app.innerHTML = `<div class="loading">…</div>`;
  try {
    await view(...hash.match(re).slice(1));
  } catch (e) {
    $app.innerHTML = `<section class="card error">${esc(errMsg(e))}</section>`;
  }
  window.scrollTo(0, 0);
}

function renderNav() {
  const nav = document.getElementById("nav");
  document.getElementById("logout").hidden = !Api.token;
  document.getElementById("lang-toggle").textContent = I18n.lang === "en" ? "BM" : "EN";
  document.getElementById("logout").textContent = t("logout");
  if (!Api.token) { nav.innerHTML = ""; return; }
  const items = [["#/home", t("nav_home")]];
  if (Api.user?.role === "student") items.push(["#/transcript", t("nav_transcript")]);
  nav.innerHTML = items.map(([h, l]) => `<a href="${h}" class="${location.hash.startsWith(h) ? "active" : ""}">${esc(l)}</a>`).join("");
}

document.getElementById("lang-toggle").onclick = () => { I18n.setLang(I18n.lang === "en" ? "ms" : "en"); router(); };
document.getElementById("logout").onclick = () => { Api.setSession(null, null); location.hash = "#/login"; };
window.addEventListener("hashchange", router);
I18n.setLang(I18n.lang);
router();

// ---------------------------------------------------------------- login
async function viewLogin() {
  if (Api.token) { location.hash = "#/home"; return; }
  const demo = [["lecturer@tempa.my", "Lecturer · Dr. Aisyah"], ["ravi@student.tempa.my", "Ravi (coasting)"],
    ["amir@student.tempa.my", "Amir (carrying)"], ["daniel@student.tempa.my", "Daniel (fresh)"]];
  $app.innerHTML = `
    <section class="hero">
      <h1>${esc(t("tagline"))}</h1>
      <p>${esc(t("pitch"))}</p>
    </section>
    <section class="card narrow">
      <div class="tabs"><button class="tab active" data-tab="login">${t("login")}</button><button class="tab" data-tab="register">${t("register")}</button></div>
      <form id="auth">
        <label class="reg-only" hidden>${t("name")}<input name="name" autocomplete="name"></label>
        <label>${t("email")}<input name="email" type="email" required autocomplete="email"></label>
        <label>${t("password")}<input name="password" type="password" required minlength="8" autocomplete="current-password"></label>
        <button class="btn primary" type="submit">${t("login")}</button>
      </form>
      <p class="muted small">${t("demo_hint")}</p>
      <div class="demo-list">${demo.map(([e, l]) => `<button class="chip" data-email="${e}">${esc(l)}</button>`).join("")}</div>
    </section>`;
  let mode = "login";
  const form = $app.querySelector("#auth");
  $app.querySelectorAll(".tab").forEach((b) => (b.onclick = () => {
    mode = b.dataset.tab;
    $app.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
    form.querySelector(".reg-only").hidden = mode !== "register";
    form.querySelector("button").textContent = t(mode);
  }));
  $app.querySelectorAll("[data-email]").forEach((b) => (b.onclick = () => {
    form.email.value = b.dataset.email; form.password.value = "demo1234"; form.requestSubmit();
  }));
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const body = { email: form.email.value, password: form.password.value };
    if (mode === "register") body.name = form.name.value;
    try {
      const r = await Api.post(`/api/auth/${mode}`, body);
      Api.setSession(r.token, r.user);
      location.hash = "#/home";
    } catch (e) { toast(errMsg(e), "bad"); }
  };
}

// ---------------------------------------------------------------- home
async function viewHome() {
  const [courses, home] = await Promise.all([Api.get("/api/courses"), Api.user.role === "student" ? Api.get("/api/home") : null]);
  const isLect = Api.user.role === "lecturer";
  const courseCards = courses.map((c) => `
    <a class="card link" href="${isLect ? `#/dashboard/${c.id}` : `#/course/${c.id}`}">
      <span class="eyebrow">${esc(c.code)}</span><h3>${esc(L(c, "title"))}</h3>
      <span class="muted">${isLect ? t("nav_dashboard") : `${t("learn")} · ${t("bounty_board")}`} →</span>
    </a>`).join("");
  if (isLect) {
    $app.innerHTML = `<h1>${esc(Api.user.name)}</h1><h2>${t("courses")}</h2><div class="grid">${courseCards}</div>`;
    return;
  }
  const p = home.pace;
  $app.innerHTML = `
    <h1>${I18n.lang === "ms" ? "Hai" : "Hi"}, ${esc(Api.user.name.split(" ")[0])}</h1>
    <div class="stats">
      <div class="stat"><span class="num">${home.points}</span><span>${t("points")}</span></div>
      <div class="stat"><span class="num">${home.streak}🔥</span><span>${t("streak")}</span></div>
      <div class="stat pace-${p.label}"><span class="num small-num">${t(`pace_${p.label}`)}</span><span>${t("pace")}</span></div>
    </div>
    <p class="muted small">${t(`pace_${p.label}_d`)}</p>
    <h2>${t("badges")}</h2>
    <div class="badges">${home.badges.length ? home.badges.map((b) => {
      const [icon, en, ms] = BADGES[b] || ["🏅", b, b];
      return `<span class="badge"><span>${icon}</span>${esc(I18n.lang === "ms" ? ms : en)}</span>`;
    }).join("") : `<p class="muted">${t("no_badges")}</p>`}</div>
    <h2>${t("courses")}</h2><div class="grid">${courseCards}</div>
    <h2>${t("recent")}</h2>
    <ul class="activity">${home.recent.map((r) => `
      <li><span class="kind k-${r.kind}">${t(`k_${r.kind}`)}</span><span>${esc(r.note)}</span><b>+${r.points}</b><time>${fmtDate(r.at)}</time></li>`).join("")}
    </ul>`;
}

// ---------------------------------------------------------------- course
async function viewCourse(id) {
  const [courses, modules, squads] = await Promise.all([
    Api.get("/api/courses"), Api.get(`/api/courses/${id}/modules`), Api.get(`/api/courses/${id}/my-squads`)]);
  const course = courses.find((c) => c.id == id);
  $app.innerHTML = `
    <span class="eyebrow">${esc(course?.code)}</span><h1>${esc(L(course || {}, "title"))}</h1>
    <h2>${t("modules")}</h2>
    <div class="grid">${modules.map((m) => `
      <a class="card link" href="#/module/${m.id}">
        <h3>${esc(L(m, "title"))}</h3>
        <div class="bar"><span style="width:${(m.done / m.sections) * 100}%"></span></div>
        <span class="muted small">${t("sections_done", { done: m.done, total: m.sections })}</span>
      </a>`).join("")}</div>
    <h2>${t("squads")}</h2>
    <div class="grid">${squads.map((s) => `
      <a class="card link" href="#/squad/${s.id}">
        <h3>${esc(s.name)}</h3><p class="muted">${esc(L(s, "project"))}</p>
        <div class="avatars">${s.members.map((m) => `<span class="avatar" title="${esc(m.name)}">${esc(m.name[0])}</span>`).join("")}</div>
        <span class="muted small">${t("bounty_board")} →</span>
      </a>`).join("")}</div>`;
}

// ---------------------------------------------------------------- module reader + Pace Gate
async function viewModule(moduleId, sectionId) {
  const mod = await Api.get(`/api/modules/${moduleId}`);
  const current = mod.sections.find((s) => s.status === "current");
  const target = sectionId ? mod.sections.find((s) => s.id == sectionId) : current || mod.sections[mod.sections.length - 1];
  const stepper = mod.sections.map((s) => `
    <a class="step ${s.status} ${s.id === target.id ? "here" : ""}" ${s.status !== "locked" ? `href="#/module/${mod.id}/${s.id}"` : ""} title="${esc(L(s, "heading"))}">
      ${s.status === "done" ? "✓" : s.status === "locked" ? "🔒" : s.position}
    </a>`).join("");

  $app.innerHTML = `
    <a class="back" href="#/course/${mod.course_id}">← ${t("back_to_course")}</a>
    <h1>${esc(L(mod, "title"))}</h1>
    <div class="stepper">${stepper}</div>
    <div id="reader"></div>`;
  await renderSection(mod, target);
}

async function renderSection(mod, target) {
  const box = document.getElementById("reader");
  const s = await Api.get(`/api/sections/${target.id}`);
  const isDone = s.status === "done";
  box.innerHTML = `
    <article class="card reading" id="article">
      <h2>${esc(L(s, "heading"))}</h2>
      ${L(s, "body").split("\n\n").map((p) => `<p>${esc(p)}</p>`).join("")}
    </article>
    <div id="gate"></div>
    <div class="reader-bar">
      ${isDone ? nextLink(mod, s) : `
        <div class="timer"><div class="bar"><span id="tbar"></span></div><small id="tlabel">${t("reading")} · ${t("suggested", { s: s.suggested_seconds })}</small></div>
        <button class="btn primary" id="done">${t("continue")}</button>`}
    </div>`;
  if (isDone) return;

  // Telemetry: these only make the verdict stricter; the server clock decides elapsed time.
  const tel = { depth: 0, velSum: 0, velN: 0, hiddenMs: 0 };
  let lastY = scrollY, lastT = performance.now(), hiddenAt = null;
  const started = performance.now();
  const article = document.getElementById("article");
  const measure = () => {
    const r = article.getBoundingClientRect();
    tel.depth = Math.max(tel.depth, Math.min(1, (innerHeight - r.top) / r.height));
  };
  const onScroll = () => {
    const now = performance.now(), dt = (now - lastT) / 1000;
    if (dt > 0.03) {
      tel.velSum += Math.abs(scrollY - lastY) / dt; tel.velN++;
      lastY = scrollY; lastT = now;
    }
    measure();
  };
  const onVis = () => {
    if (document.hidden) hiddenAt = performance.now();
    else if (hiddenAt) { tel.hiddenMs += performance.now() - hiddenAt; hiddenAt = null; }
  };
  const tick = setInterval(() => {
    const f = Math.min(1, (performance.now() - started) / 1000 / s.suggested_seconds);
    const bar = document.getElementById("tbar");
    if (!bar) return;
    bar.style.width = `${f * 100}%`;
    if (f >= 1) document.getElementById("tlabel").textContent = t("ready");
  }, 250);
  addEventListener("scroll", onScroll, { passive: true });
  document.addEventListener("visibilitychange", onVis);
  measure();
  cleanup = () => { clearInterval(tick); removeEventListener("scroll", onScroll); document.removeEventListener("visibilitychange", onVis); };

  if (s.gate) showGate(mod, s, s.gate, []);
  document.getElementById("done").onclick = async () => {
    const r = await Api.post(`/api/sections/${s.id}/complete`, {
      scroll_depth: +tel.depth.toFixed(3),
      avg_scroll_velocity: tel.velN ? Math.round(tel.velSum / tel.velN) : 0,
      hidden_ms: Math.round(tel.hiddenMs),
    });
    if (r.unlocked) { toast(t("unlocked_read", { p: r.points }), "good"); router(); }
    else showGate(mod, s, r.gate, r.reasons);
  };
}

function showGate(mod, s, gate, reasons) {
  const el = document.getElementById("gate");
  const opts = gate.options[I18n.lang] || gate.options.en;
  el.innerHTML = `
    <section class="card gate">
      <h3>🔐 ${t("gate_title")}</h3>
      <p>${t("gate_intro")}</p>
      ${reasons.length ? `<div class="reasons">${reasons.map((r) => `<span class="chip warn">${t(`reason_${r}`)}</span>`).join("")}</div>` : ""}
      <p class="q">${esc(L(gate, "question"))}</p>
      <div class="options">${opts.map((o, i) => `<button class="option" data-i="${i}">${esc(o)}</button>`).join("")}</div>
    </section>`;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.querySelectorAll(".option").forEach((b) => (b.onclick = async () => {
    const r = await Api.post(`/api/sections/${s.id}/checkpoint`, { choice: +b.dataset.i });
    if (r.correct) {
      toast(`${t("unlocked_cp", { p: r.points })} ${L(r, "explanation")}`, "good");
      router();
    } else {
      el.innerHTML = `<section class="card gate bad"><p>${t("wrong")}</p>
        <button class="btn" id="reread">${t("reread")}</button></section>`;
      document.getElementById("reread").onclick = () => router();
    }
  }));
}

function nextLink(mod, s) {
  const idx = mod.sections.findIndex((x) => x.id === s.id);
  const next = mod.sections[idx + 1];
  if (next && next.status !== "locked") return `<a class="btn primary" href="#/module/${mod.id}/${next.id}">${t("next_section")} →</a>`;
  if (!next) return `<span class="done-msg">${t("module_done")}</span><a class="btn" href="#/course/${mod.course_id}">${t("back_to_course")}</a>`;
  return "";
}

// ---------------------------------------------------------------- bounty board
async function viewSquad(id) {
  const d = await Api.get(`/api/squads/${id}/board`);
  const me = Api.user.id;
  const cols = ["open", "claimed", "submitted", "verified"];
  const c = d.contributions;
  $app.innerHTML = `
    <a class="back" href="javascript:history.back()">←</a>
    <h1>${esc(d.squad.name)}</h1><p class="muted">${esc(L(d.squad, "project"))}</p>
    <section class="card">
      <div class="row between"><h3>${t("contribution")}</h3><span class="muted small">${t("fair_share", { p: pct(c.fair_share) })}</span></div>
      <div class="bar big"><span style="width:${pct(c.progress)}%"></span></div>
      <p class="muted small">${t("progress")}: ${c.total_earned}/${c.total_available} ${t("pts")}</p>
      ${c.members.map((m) => `
        <div class="contrib ${m.status}">
          <span class="who">${esc(m.name)}${m.user_id === me ? " ★" : ""}</span>
          <div class="bar"><span style="width:${pct(m.share)}%"></span><i style="left:${pct(c.fair_share)}%"></i></div>
          <span class="pts">${m.points} ${t("pts")}</span>
          <span class="chip s-${m.status}">${t(`s_${m.status}`)}</span>
        </div>`).join("")}
      <p class="muted small">${t("claim_ttl", { h: d.claim_ttl_hours })}</p>
    </section>
    <div class="board">${cols.map((col) => `
      <div class="col"><h3>${t(`st_${col}`)} <span class="count">${d.bounties.filter((b) => b.status === col).length}</span></h3>
        ${d.bounties.filter((b) => b.status === col).map((b) => `
          <div class="bounty">
            <div class="row between"><span class="tag">${esc(b.skill_tag)}</span><b class="reward">${b.points} ${t("pts")}</b></div>
            <h4>${b.kind === "code" ? "⌨️" : "📐"} ${esc(L(b, "title"))}</h4>
            ${b.claimed_by ? `<span class="muted small">${t("claimed_by", { n: esc(b.claimed_by.name) })}</span>` : ""}
            <div class="row">
              ${col === "open" && Api.user.role === "student" ? `<button class="btn small primary" data-claim="${b.id}">${t("claim")}</button>` : ""}
              <a class="btn small" href="#/bounty/${b.id}">${t("view")}</a>
            </div>
          </div>`).join("")}
      </div>`).join("")}
    </div>`;
  $app.querySelectorAll("[data-claim]").forEach((b) => (b.onclick = async () => {
    try { await Api.post(`/api/bounties/${b.dataset.claim}/claim`); location.hash = `#/bounty/${b.dataset.claim}`; }
    catch (e) { toast(errMsg(e), "bad"); }
  }));
}

async function viewBounty(id) {
  const b = await Api.get(`/api/bounties/${id}`);
  const mine = b.claimed_by?.id === Api.user.id;
  const canWork = mine && (b.status === "claimed" || b.status === "submitted");
  const ch = b.challenge;
  $app.innerHTML = `
    <a class="back" href="#/squad/${b.squad_id}">← ${t("bounty_board")}</a>
    <div class="row between"><h1>${esc(L(b, "title"))}</h1><b class="reward big">${b.points} ${t("pts")}</b></div>
    <p><span class="chip st-${b.status}">${t(`st_${b.status}`)}</span> <span class="tag">${esc(b.skill_tag)}</span>
      ${b.claimed_by ? `<span class="muted small">${t("claimed_by", { n: esc(b.claimed_by.name) })}</span>` : ""}</p>
    <p>${esc(L(b, "description"))}</p>
    ${ch ? `
      <section class="card"><h3>${esc(L(ch, "title"))}</h3><p>${esc(L(ch, "prompt"))}</p>
        <h4>${t("visible_tests")}</h4>
        <ul class="tests">${ch.visible_tests.map((x) => `<li><code>${esc(ch.function_name)}(${x.args.map((a) => JSON.stringify(a)).join(", ")}) → ${esc(JSON.stringify(x.expected))}</code></li>`).join("")}</ul>
        <p class="muted small">${t("hidden_tests", { n: ch.hidden_count })}</p>
      </section>` : ""}
    ${canWork ? `
      <section class="card">
        <textarea id="code" class="${ch ? "code" : ""}" spellcheck="false" placeholder="${ch ? "" : esc(t("artifact_ph"))}">${ch ? esc(lastCode(b) || ch.starter_code) : ""}</textarea>
        <div class="row">
          ${ch ? `<button class="btn" id="run">${t("run_tests")}</button>` : ""}
          <button class="btn primary" id="submit">${ch ? t("submit") : t("submit_artifact")}</button>
          <button class="btn ghost" id="release">${t("release")}</button>
        </div>
        <div id="result"></div>
      </section>` : b.status === "open" ? `<p class="muted">${t("claim_first")}</p>` : ""}
    ${b.submissions.length ? `<h3>${t("submissions")}</h3>
      <ul class="activity">${b.submissions.map((s) => `<li><span class="chip v-${s.verdict}">${s.verdict}</span>
        <span>${s.total ? t("passed", { p: s.passed, t: s.total }) : ""} ${esc(s.feedback)}</span><time>${fmtDate(s.created_at)}</time></li>`).join("")}</ul>` : ""}`;
  if (!canWork) return;

  const code = document.getElementById("code");
  code.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    e.preventDefault();
    const { selectionStart: a, selectionEnd: z } = code;
    code.setRangeText("    ", a, z, "end");
  });
  const out = document.getElementById("result");
  if (ch) document.getElementById("run").onclick = async () => {
    out.innerHTML = "…";
    out.innerHTML = renderResult(await Api.post(`/api/challenges/${ch.slug}/run`, { code: code.value }));
  };
  document.getElementById("submit").onclick = async () => {
    out.innerHTML = "…";
    try {
      const r = await Api.post(`/api/bounties/${b.id}/submit`, { content: code.value, lang: I18n.lang });
      if (r.verdict === "pass") { toast(t("verdict_pass"), "good"); setTimeout(() => (location.hash = `#/squad/${b.squad_id}`), 900); }
      else if (r.verdict === "pending_review") { toast(t("verdict_review"), "good"); router(); return; }
      out.innerHTML = `<p class="verdict ${r.verdict}">${t(`verdict_${r.verdict}`)}</p>${renderResult(r.result)}
        ${r.hint ? `<div class="coach"><b>💡 ${t("coach")}</b> <span class="chip">${t(r.hint.source === "ai" ? "coach_ai" : "coach_rules")}</span><p>${esc(r.hint.text)}</p></div>` : ""}`;
    } catch (e) { toast(errMsg(e), "bad"); }
  };
  document.getElementById("release").onclick = async () => { await Api.post(`/api/bounties/${b.id}/release`); location.hash = `#/squad/${b.squad_id}`; };
}

function lastCode(b) { return b.submissions.find((s) => s.content)?.content; }

function renderResult(r) {
  if (r.error) return `<pre class="err">${esc(r.error)}</pre>`;
  return `<p><b>${t("passed", { p: r.passed, t: r.total })}</b></p><ul class="cases">${r.cases.map((c) => `
    <li class="${c.ok ? "ok" : "fail"}">${c.ok ? "✓" : "✗"} #${c.n} ${c.hidden ? "🔒" :
      `<code>${esc(JSON.stringify(c.args))}</code> → <code>${esc(JSON.stringify(c.got ?? c.error))}</code>${c.ok ? "" : ` ≠ <code>${esc(JSON.stringify(c.expected))}</code>`}`}</li>`).join("")}</ul>`;
}

// ---------------------------------------------------------------- transcript
function transcriptHtml(d, isPublic) {
  const shareUrl = `${location.origin}${location.pathname}#/t/${d.student.public_id}`;
  const maxSkill = Math.max(1, ...Object.values(d.skills).map((s) => s.points));
  return `
    <span class="eyebrow">${t("transcript_title")}</span><h1>${esc(d.student.name)}</h1>
    <p class="integrity ${d.integrity.valid ? "ok" : "bad"}">${d.integrity.valid ? `✔ ${t("integrity_ok")}` : `✖ ${t("integrity_bad", { n: d.integrity.broken_at_seq })}`}
      ${d.integrity.head ? `<code title="chain head">${d.integrity.head.slice(0, 16)}…</code>` : ""}</p>
    ${isPublic ? `<p class="muted small">${t("public_note")}</p>` : `
      <div class="share"><label>${t("share_link")}<input readonly value="${esc(shareUrl)}" id="share"></label><button class="btn small" id="copy">${t("copy")}</button></div>`}
    <div class="stats">
      <div class="stat"><span class="num">${d.total_points}</span><span>${t("total")}</span></div>
      <div class="stat"><span class="num">${d.verified_bounties}</span><span>${t("verified_bounties")}</span></div>
    </div>
    <h2>${t("skills")}</h2>
    ${Object.entries(d.skills).map(([k, v]) => `<div class="skill"><span>${esc(k)}</span><div class="bar"><span style="width:${(v.points / maxSkill) * 100}%"></span></div><b>${v.points}</b></div>`).join("")}
    <h2>${t("ledger")}</h2>
    <ul class="activity">${d.entries.map((e) => `<li><span class="kind k-${e.kind}">#${e.seq} ${t(`k_${e.kind}`)}</span><span>${esc(e.note)}</span><b>+${e.points}</b><time>${fmtDate(e.at)}</time><code class="hash">${e.hash.slice(0, 10)}</code></li>`).join("")}</ul>`;
}

async function viewTranscript() {
  $app.innerHTML = transcriptHtml(await Api.get("/api/transcript/me"), false);
  document.getElementById("copy").onclick = () => {
    navigator.clipboard?.writeText(document.getElementById("share").value).then(() => toast(t("copied"), "good"));
  };
}

async function viewPublicTranscript(publicId) {
  $app.innerHTML = transcriptHtml(await Api.get(`/api/public/transcript/${publicId}`), true);
}

// ---------------------------------------------------------------- lecturer dashboard
async function viewDashboard(courseId) {
  const d = await Api.get(`/api/courses/${courseId}/dashboard`);
  $app.innerHTML = `
    <span class="eyebrow">${esc(d.course.code)}</span><h1>${esc(L(d.course, "title"))}</h1>
    <div class="stats">
      <div class="stat"><span class="num">${d.students}</span><span>${t("dash_students")}</span></div>
      <div class="stat"><span class="num">${d.review_queue.length}</span><span>${t("dash_reviews")}</span></div>
    </div>
    <h2>${t("dash_squads")}</h2>
    <div class="grid">${d.squads.map((s) => `
      <a class="card link" href="#/squad/${s.id}">
        <h3>${esc(s.name)}</h3>
        <div class="bar"><span style="width:${pct(s.progress)}%"></span></div>
        ${s.members.map((m) => `<div class="contrib compact ${m.status}"><span class="who">${esc(m.name)}</span>
          <div class="bar"><span style="width:${pct(m.share)}%"></span><i style="left:${pct(s.fair_share)}%"></i></div>
          <span class="chip s-${m.status}">${t(`s_${m.status}`)}</span></div>`).join("")}
      </a>`).join("")}</div>
    <h2>${t("dash_modules")}</h2>
    <div class="table-wrap"><table>
      <thead><tr><th></th><th>${t("completions")}</th><th>${t("via_read")}</th><th>${t("via_cp")}</th><th>${t("rushes")}</th><th>${t("accuracy")}</th></tr></thead>
      <tbody>${d.modules.map((m) => `<tr><td>${esc(L(m, "title"))}</td><td>${m.completions}</td><td>${m.via_reading}</td><td>${m.via_checkpoint}</td>
        <td>${m.rush_events}</td><td>${m.first_try_accuracy == null ? "–" : pct(m.first_try_accuracy) + "%"}</td></tr>`).join("")}</tbody>
    </table></div>
    <h2>${t("review_queue")}</h2>
    ${d.review_queue.length ? d.review_queue.map((r) => `
      <section class="card">
        <div class="row between"><h3>${esc(L(r, "title"))}</h3><span class="muted">${esc(r.claimed_by)}</span></div>
        <pre class="artifact">${esc(r.content)}</pre>
        <div class="row"><button class="btn primary" data-review="${r.bounty_id}" data-ok="1">${t("approve")}</button>
          <button class="btn" data-review="${r.bounty_id}" data-ok="0">${t("reject")}</button></div>
      </section>`).join("") : `<p class="muted">${t("nothing")}</p>`}
    <h2>${t("matching")}</h2>
    <section class="card">
      <form id="match" class="row">
        <label>${t("size")}<input name="size" type="number" min="2" max="8" value="3"></label>
        <label>${t("mode")}<select name="mode"><option value="balanced">${t("balanced")}</option><option value="tiered">${t("tiered")}</option></select></label>
        <button class="btn" name="go" value="preview">${t("preview")}</button>
        <button class="btn primary" name="go" value="apply">${t("apply")}</button>
      </form>
      <div id="proposal" class="grid"></div>
    </section>`;

  $app.querySelectorAll("[data-review]").forEach((b) => (b.onclick = async () => {
    await Api.post(`/api/bounties/${b.dataset.review}/review`, { approve: b.dataset.ok === "1" });
    router();
  }));
  const form = document.getElementById("match");
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const apply = ev.submitter?.value === "apply";
    const r = await Api.post(`/api/courses/${courseId}/match`, { squad_size: +form.size.value, mode: form.mode.value, apply });
    document.getElementById("proposal").innerHTML = r.squads.map((s) => `
      <div class="card"><h4>${esc(s.name)}</h4><p class="muted small">avg ${s.avg_competence} ${t("competence")}</p>
        <ul>${s.members.map((m) => `<li>${esc(m.name)} <span class="muted">(${m.competence})</span></li>`).join("")}</ul></div>`).join("");
    if (apply) toast("✓", "good");
  };
}
