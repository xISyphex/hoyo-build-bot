// The optimizer page: loads the pickers' data and the player's session, keeps the configuration, runs the search.

import { ApiError, api, forgetToken, takeToken } from "./api.js";
import { $, clear, h, icon, segmented } from "./dom.js";
import { openPicker, showChoice } from "./picker.js";
import { showBusy, showError, showResult } from "./result.js";

const PERCENT_FLAT = new Set(["SpeedDelta", "HPDelta", "AttackDelta", "DefenceDelta"]);
const token = takeToken();

const S = {
  meta: null, session: null,
  chars: new Map(), cones: new Map(), relicSets: new Map(), planarSets: new Map(), owned: new Map(),
  main: null,  // {id, level, ascension, eidolon, abilities, traces:Set, cone:{id, level, rank}|null}
  sets: { relic: null, planar: null },
  speed: null,
  exclude: [],
  team: [null, null, null],  // {id, eidolon, cone:{id, rank}|null, relic_set, planar_set}
  running: false,
};

// ---- page states ------------------------------------------------------------------------------------------------

function show(which) {
  for (const id of ["state-loading", "state-expired", "state-error", "workspace"]) $(id).hidden = id !== which;
}

function expired() {
  forgetToken();
  $("session-info").hidden = true;
  show("state-expired");
}

function failed(error) {
  if (error instanceof ApiError && error.status === 401) return expired();
  $("state-error-text").textContent = error instanceof ApiError && error.status === 0 ? error.message
    : "The optimizer couldn't load. Try again in a moment.";
  show("state-error");
}

// ---- options for the pickers ------------------------------------------------------------------------------------

function charOption(c) {
  const mine = S.owned.get(c.id);
  return {
    id: c.id, name: c.name, icon: c.icon, rarity: c.rarity, owned: Boolean(mine),
    sub: `${c.path} · ${c.element}${mine ? ` · Lv. ${mine.level} E${mine.eidolon}` : ""}`,
    tags: [mine ? "Owned" : null, c.unreleased ? "Beta" : null].filter(Boolean), search: c.path,
  };
}

function characterOptions(skip = []) {
  return S.meta.characters.filter((c) => !skip.includes(c.id)).map(charOption)
    .sort((a, b) => (b.owned - a.owned) || (b.rarity - a.rarity) || a.name.localeCompare(b.name));
}

function characterFilters() {
  const paths = [...new Set(S.meta.characters.map((c) => c.path))].filter(Boolean).sort();
  return [{ label: "All" }, { label: "Owned", test: (o) => o.owned }, ...paths.map((p) => ({ label: p, test: (o) => S.chars.get(o.id)?.path === p }))];
}

function wornCones() {
  const worn = new Map();
  for (const c of S.session.characters) if (c.light_cone) {
    if (!worn.has(c.light_cone.id)) worn.set(c.light_cone.id, []);
    worn.get(c.light_cone.id).push(c.name);
  }
  return worn;
}

function coneOption(lc, path) {
  const worn = wornCones().get(lc.id);
  return { id: lc.id, name: lc.name, icon: lc.icon, rarity: lc.rarity, sub: lc.path + (worn ? ` · worn by ${worn.join(", ")}` : ""),
    tags: [path && lc.path === path ? "Path" : null].filter(Boolean), worn: Boolean(worn) };
}

function coneOptions(path) {
  const none = { id: null, name: "No light cone" };
  const all = S.meta.light_cones.map((lc) => coneOption(lc, path))
    .sort((a, b) => ((S.cones.get(b.id).path === path) - (S.cones.get(a.id).path === path)) || (b.worn - a.worn) || (b.rarity - a.rarity) || a.name.localeCompare(b.name));
  return [none, ...all];
}

function coneFilters(path) {
  return [{ label: "All" }, path ? { label: path, test: (o) => S.cones.get(o.id)?.path === path } : null,
    { label: "On my account", test: (o) => o.worn }].filter(Boolean);
}

function setOption(s, recommended) {
  return { id: s.id, name: s.name, icon: s.icon, sub: s.bonus_2pc || "", tags: recommended.includes(s.id) ? ["Recommended"] : [],
    search: `${s.bonus_2pc || ""} ${s.bonus_4pc || ""}` };
}

function setOptions(planar, characterId, noneLabel) {
  const sets = planar ? S.meta.planar_sets : S.meta.relic_sets;
  const recommended = (S.chars.get(characterId)?.recommended || {})[planar ? "planar" : "relic"] || [];
  const first = recommended.map((id) => (planar ? S.planarSets : S.relicSets).get(id)).find(Boolean);
  const none = { id: null, name: noneLabel || (first ? `Game's pick: ${first.name}` : "Game's pick"),
    sub: first ? "The set the game recommends first" : "" };
  const list = sets.map((s) => setOption(s, recommended)).sort((a, b) => (b.tags.length - a.tags.length));
  return [none, ...list];
}

// ---- the main character -------------------------------------------------------------------------------------------

function fits(level, ascension) {
  return level <= 20 + 10 * ascension && (ascension === 0 || level >= 10 + 10 * ascension);
}

function minAscension(level) {
  return Math.max(0, Math.min(6, Math.ceil((level - 20) / 10)));
}

function fromOwned(c, meta) {
  const abilities = {};
  for (const a of meta.abilities) abilities[a.id] = Math.min(c.abilities[a.id] || 1, a.max_level);
  const known = new Set(meta.traces.map((t) => t.id));
  return {
    id: meta.id, level: c.level, ascension: fits(c.level, c.ascension) ? c.ascension : minAscension(c.level), eidolon: c.eidolon,
    abilities, traces: new Set(c.traces.filter((t) => known.has(t))),
    cone: c.light_cone && S.cones.has(c.light_cone.id) ? { ...c.light_cone } : null,
  };
}

function maxed(meta, keep = {}) {
  const abilities = {};
  for (const a of meta.abilities) abilities[a.id] = a.max_level;
  return { id: meta.id, level: 80, ascension: 6, eidolon: keep.eidolon ?? 0, abilities, traces: new Set(meta.traces.map((t) => t.id)),
    cone: keep.cone ?? null };
}

function chooseMain(id) {
  const meta = S.chars.get(id);
  if (!meta) return;
  const mine = S.owned.get(id);
  S.main = mine ? fromOwned(mine, meta) : maxed(meta);
  S.sets = { relic: null, planar: null };
  S.team = S.team.map((m) => (m && m.id === id ? null : m));
  renderMain();
  renderSets();
  renderTeam();
  updateGo();
}

function renderMain() {
  const trigger = $("pick-character");
  const details = $("character-details");
  if (!S.main) {
    showChoice(trigger, null, "Choose a character");
    details.hidden = true;
    renderCone();
    return;
  }
  const meta = S.chars.get(S.main.id);
  showChoice(trigger, charOption(meta), "Choose a character");
  details.hidden = false;
  $("char-owned").hidden = !S.owned.has(meta.id);

  const level = $("char-level");
  level.value = S.main.level;
  renderAscension();
  segmented($("char-eidolon"), [0, 1, 2, 3, 4, 5, 6].map((e) => ({ value: e, label: `E${e}`, title: e ? meta.eidolons[e - 1] : "No eidolons" })),
    S.main.eidolon, (e) => { S.main.eidolon = e; eidolonHint(meta); });
  eidolonHint(meta);

  const abilities = clear($("char-abilities"));
  if (!meta.abilities.length) abilities.append(h("p", { class: "hint", text: "No ability data for this character yet." }));
  for (const a of meta.abilities) {
    const id = `ab-${a.id}`;
    const input = h("input", { type: "number", id, min: 1, max: a.max_level, value: S.main.abilities[a.id], inputmode: "numeric" });
    input.addEventListener("input", () => { S.main.abilities[a.id] = Number(input.value); updateGo(); });
    abilities.append(h("label", { class: "ability", for: id },
      h("span", {}, h("span", { class: "kind", text: `${a.type} · max ${a.max_level}` }), h("span", { class: "name", text: a.name })), input));
  }

  const traces = clear($("char-traces"));
  if (!meta.traces.length) traces.append(h("p", { class: "hint", text: "No trace data for this character yet." }));
  for (const t of meta.traces) {
    const label = t.kind === "stat" ? statLabel(t.stat) : t.name;
    const button = h("button", { type: "button", class: `trace ${t.kind}`, "aria-pressed": String(S.main.traces.has(t.id)),
      title: t.kind === "stat" ? t.name : t.desc, text: label });
    button.addEventListener("click", () => {
      const on = !S.main.traces.has(t.id);
      if (on) S.main.traces.add(t.id); else S.main.traces.delete(t.id);
      button.setAttribute("aria-pressed", String(on));
    });
    traces.append(button);
  }
  renderCone();
}

function statLabel(stat) {
  const name = stat.name.replace(/%$/, "");
  const value = PERCENT_FLAT.has(stat.type) ? `${+stat.value.toFixed(1)}` : `${+(stat.value * 100).toFixed(1)}%`;
  return `${name} +${value}`;
}

function eidolonHint(meta) {
  $("char-eidolon-name").textContent = S.main.eidolon ? `E${S.main.eidolon}: ${meta.eidolons[S.main.eidolon - 1]}` : "No eidolons";
}

function renderAscension() {
  const select = clear($("char-ascension"));
  for (let a = 0; a <= 6; a++) {
    select.append(h("option", { value: a, disabled: !fits(S.main.level, a), selected: a === S.main.ascension,
      text: `A${a} (up to Lv. ${20 + 10 * a})` }));
  }
}

function renderCone() {
  const trigger = $("pick-cone");
  const cone = S.main && S.main.cone;
  const lc = cone && S.cones.get(cone.id);
  showChoice(trigger, lc ? coneOption(lc, S.main && S.chars.get(S.main.id).path) : null, S.main ? "No light cone" : "Choose a character first");
  trigger.disabled = !S.main;
  $("cone-level").value = cone ? cone.level : 80;
  $("cone-level").disabled = !cone;
  segmented($("cone-rank"), [1, 2, 3, 4, 5].map((r) => ({ value: r, label: `S${r}` })), cone ? cone.rank : 1,
    (r) => { if (S.main && S.main.cone) S.main.cone.rank = r; });
  for (const b of $("cone-rank").children) b.disabled = !cone;
}

// ---- sets and options -------------------------------------------------------------------------------------------

function renderSets() {
  const cid = S.main && S.main.id;
  const relic = setOptions(false, cid).find((o) => o.id === S.sets.relic);
  const planar = setOptions(true, cid).find((o) => o.id === S.sets.planar);
  const face = (o) => o && { ...o, sub: o.tags && o.tags.length ? "Recommended" : o.id ? "" : o.sub };
  showChoice($("pick-relic-set"), face(S.sets.relic ? relic : setOptions(false, cid)[0]), "Game's pick");
  showChoice($("pick-planar-set"), face(S.sets.planar ? planar : setOptions(true, cid)[0]), "Game's pick");
}

function renderExclude() {
  const box = clear($("exclude-chips"));
  for (const id of S.exclude) {
    const c = S.owned.get(id);
    const meta = S.chars.get(id);
    if (!c) continue;
    box.append(h("span", { class: "chip" }, icon(meta && meta.icon, c.name, meta && meta.rarity), c.name,
      h("button", { type: "button", "aria-label": `Stop keeping ${c.name}'s relics`, text: "×",
        onclick: () => { S.exclude = S.exclude.filter((x) => x !== id); renderExclude(); $("exclude-add").focus(); } })));
  }
  $("exclude-add").disabled = S.owned.size === 0 || S.exclude.length >= S.owned.size;
}

// ---- the team -----------------------------------------------------------------------------------------------------

function wornSets(characterId) {
  const counts = {};
  for (const r of S.session.relics) if (r.owner === characterId && r.set_id) counts[r.set_id] = (counts[r.set_id] || 0) + 1;
  const pick = (sets, need) => Object.keys(counts).find((id) => sets.has(id) && counts[id] >= need) || null;
  return { relic: pick(S.relicSets, 4), planar: pick(S.planarSets, 2) };
}

function mateFrom(id) {
  const mine = S.owned.get(id);
  const sets = mine ? wornSets(id) : { relic: null, planar: null };
  return { id, eidolon: mine ? mine.eidolon : 0, cone: mine && mine.light_cone && S.cones.has(mine.light_cone.id)
    ? { id: mine.light_cone.id, rank: mine.light_cone.rank } : null, relic_set: sets.relic, planar_set: sets.planar };
}

function teamSkip(index) {
  return [S.main && S.main.id, ...S.team.filter((m, i) => m && i !== index).map((m) => m.id)].filter(Boolean);
}

function renderTeam() {
  const box = clear($("team"));
  S.team.forEach((mate, i) => {
    const slot = h("div", { class: "mate", role: "group", "aria-label": `Teammate ${i + 1}` });
    const head = h("div", { class: "mate-head" }, h("span", { class: "label", text: `Teammate ${i + 1}` }));
    const pickMate = h("button", { type: "button", class: "picker-trigger", "aria-haspopup": "dialog", dataset: { what: `Teammate ${i + 1}` } });
    pickMate.addEventListener("click", () => openPicker({
      trigger: pickMate, heading: `Teammate ${i + 1}`, options: characterOptions(teamSkip(i)), current: mate && mate.id,
      filters: characterFilters(), placeholder: "Search characters",
      onPick: (id) => { S.team[i] = mateFrom(id); renderTeam(); },
    }));
    slot.append(head, pickMate);
    if (!mate) {
      showChoice(pickMate, null, "Add a teammate");
      box.append(slot);
      return;
    }
    const meta = S.chars.get(mate.id);
    showChoice(pickMate, charOption(meta), "Add a teammate");
    head.append(h("button", { type: "button", class: "clear", text: "Remove", "aria-label": `Remove teammate ${i + 1}`,
      onclick: () => { S.team[i] = null; renderTeam(); } }));

    const eidolon = h("select", { "aria-label": `Teammate ${i + 1} eidolons` },
      [0, 1, 2, 3, 4, 5, 6].map((e) => h("option", { value: e, selected: e === mate.eidolon, text: `E${e}` })));
    eidolon.addEventListener("change", () => { mate.eidolon = Number(eidolon.value); });
    const cone = h("button", { type: "button", class: "picker-trigger", "aria-haspopup": "dialog", dataset: { what: `Teammate ${i + 1} light cone` } });
    const lc = mate.cone && S.cones.get(mate.cone.id);
    showChoice(cone, lc ? coneOption(lc, meta.path) : null, "No light cone");
    cone.addEventListener("click", () => openPicker({
      trigger: cone, heading: `${meta.name}'s light cone`, options: coneOptions(meta.path), current: mate.cone && mate.cone.id,
      filters: coneFilters(meta.path), placeholder: "Search light cones",
      onPick: (id) => { mate.cone = id ? { id, rank: (mate.cone && mate.cone.rank) || 1 } : null; renderTeam(); },
    }));
    const rank = h("select", { "aria-label": `Teammate ${i + 1} superimposition`, disabled: !mate.cone },
      [1, 2, 3, 4, 5].map((r) => h("option", { value: r, selected: mate.cone && r === mate.cone.rank, text: `S${r}` })));
    rank.addEventListener("change", () => { if (mate.cone) mate.cone.rank = Number(rank.value); });
    const sets = ["relic_set", "planar_set"].map((key) => {
      const planar = key === "planar_set";
      const button = h("button", { type: "button", class: "picker-trigger", "aria-haspopup": "dialog",
        dataset: { what: `Teammate ${i + 1} ${planar ? "planar" : "relic"} set` } });
      const options = setOptions(planar, mate.id, planar ? "No planar set" : "No relic set");
      const chosen = options.find((o) => o.id === mate[key]) || options[0];
      showChoice(button, { ...chosen, sub: "" }, "None");
      button.addEventListener("click", () => openPicker({
        trigger: button, heading: `${meta.name}'s ${planar ? "planar" : "relic"} set`, options, current: mate[key],
        placeholder: "Search sets", onPick: (id) => { mate[key] = id; renderTeam(); },
      }));
      return button;
    });
    slot.append(h("div", { class: "mate-row" }, cone, rank), h("div", { class: "mate-row" }, sets[0], eidolon), sets[1]);
    box.append(slot);
  });
}

// ---- optimize -----------------------------------------------------------------------------------------------------

function problems() {
  if (!S.main) return "Pick a character first.";
  const meta = S.chars.get(S.main.id);
  if (!Number.isInteger(S.main.level) || S.main.level < 1 || S.main.level > 80) return "The level goes from 1 to 80.";
  for (const a of meta.abilities) {
    const v = S.main.abilities[a.id];
    if (!Number.isInteger(v) || v < 1 || v > a.max_level) return `${a.type} goes from 1 to ${a.max_level}.`;
  }
  if (S.main.cone && (!Number.isInteger(S.main.cone.level) || S.main.cone.level < 1 || S.main.cone.level > 80)) {
    return "The light cone's level goes from 1 to 80.";
  }
  return "";
}

function updateGo() {
  const problem = problems();
  $("optimize").disabled = Boolean(problem) || S.running;
  $("go-hint").textContent = S.running ? "Working…" : problem || "Tries every combination of your relics in the two sets.";
}

function request() {
  const m = S.main;
  return {
    character: {
      id: m.id, level: m.level, ascension: m.ascension, eidolon: m.eidolon, abilities: { ...m.abilities }, traces: [...m.traces],
      light_cone: m.cone ? { id: m.cone.id, level: m.cone.level, rank: m.cone.rank } : null,
    },
    teammates: S.team.filter(Boolean).map((t) => ({ id: t.id, eidolon: t.eidolon, light_cone: t.cone ? { id: t.cone.id, rank: t.cone.rank } : null,
      relic_set: t.relic_set, planar_set: t.planar_set })),
    options: { relic_set: S.sets.relic, planar_set: S.sets.planar, speed: S.speed, exclude: [...S.exclude] },
  };
}

async function optimize() {
  if (problems() || S.running) return;
  const body = $("result-body");
  S.running = true;
  updateGo();
  showBusy(body);
  try {
    const result = await api("optimize", { token, method: "POST", body: request() });
    showResult(body, result, S.chars.get(result.character.id));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return expired();
    const messages = { 400: "Some settings aren't valid:", 409: "An optimize is already running. Wait for it to finish.",
      429: "That's a lot of optimizing. Wait a few minutes, then try again." };
    showError(body, messages[error.status] || (error.body && error.body.error) || "Something went wrong. Try again.", error.body && error.body.details);
  } finally {
    S.running = false;
    updateGo();
  }
  if (matchMedia("(max-width: 979px)").matches) $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- wiring -------------------------------------------------------------------------------------------------------

function wire() {
  $("pick-character").dataset.what = "Character";
  $("pick-cone").dataset.what = "Light cone";
  $("pick-relic-set").dataset.what = "Relic set";
  $("pick-planar-set").dataset.what = "Planar set";
  $("pick-character").addEventListener("click", (event) => openPicker({
    trigger: event.currentTarget, heading: "Character", options: characterOptions(), current: S.main && S.main.id,
    filters: characterFilters(), placeholder: "Search characters", onPick: (id) => chooseMain(id),
  }));
  $("pick-cone").addEventListener("click", (event) => {
    const path = S.chars.get(S.main.id).path;
    openPicker({
      trigger: event.currentTarget, heading: "Light cone", options: coneOptions(path), current: S.main.cone && S.main.cone.id,
      filters: coneFilters(path), placeholder: "Search light cones",
      onPick: (id) => { S.main.cone = id ? { id, level: (S.main.cone && S.main.cone.level) || 80, rank: (S.main.cone && S.main.cone.rank) || 1 } : null; renderCone(); updateGo(); },
    });
  });
  for (const [key, planar] of [["relic", false], ["planar", true]]) {
    $(`pick-${key}-set`).addEventListener("click", (event) => openPicker({
      trigger: event.currentTarget, heading: planar ? "Planar set" : "Relic set", options: setOptions(planar, S.main && S.main.id),
      current: S.sets[key], placeholder: "Search sets", onPick: (id) => { S.sets[key] = id; renderSets(); },
    }));
  }
  $("exclude-add").addEventListener("click", (event) => openPicker({
    trigger: event.currentTarget, heading: "Keep relics on", placeholder: "Search your characters",
    options: characterOptions().filter((o) => o.owned && !S.exclude.includes(o.id)),
    onPick: (id) => { S.exclude.push(id); renderExclude(); },
  }));
  $("char-level").addEventListener("input", (event) => {
    S.main.level = Number(event.target.value);
    if (Number.isInteger(S.main.level) && S.main.level >= 1 && S.main.level <= 80 && !fits(S.main.level, S.main.ascension)) {
      S.main.ascension = minAscension(S.main.level);
    }
    renderAscension();
    updateGo();
  });
  $("char-ascension").addEventListener("change", (event) => { S.main.ascension = Number(event.target.value); });
  $("cone-level").addEventListener("input", (event) => { if (S.main && S.main.cone) S.main.cone.level = Number(event.target.value); updateGo(); });
  $("char-max").addEventListener("click", () => {
    S.main = maxed(S.chars.get(S.main.id), { eidolon: S.main.eidolon, cone: S.main.cone && { ...S.main.cone, level: 80 } });
    renderMain();
    updateGo();
  });
  $("char-owned").addEventListener("click", () => {
    S.main = fromOwned(S.owned.get(S.main.id), S.chars.get(S.main.id));
    renderMain();
    updateGo();
  });
  $("optimize").addEventListener("click", optimize);
  $("retry").addEventListener("click", start);
}

function sessionLine() {
  const info = $("session-info");
  const minutes = Math.max(0, Math.round((S.session.expires_at * 1000 - Date.now()) / 60000));
  clear(info).append("UID ", h("b", { text: S.session.player.uid }), ` · ${S.owned.size} characters · ${S.session.relics.length} relics · link works ${minutes > 0 ? `${minutes} more min` : "under a minute more"}`);
  info.hidden = false;
}

async function start() {
  if (!token) return expired();
  show("state-loading");
  try {
    const [meta, session] = await Promise.all([api("meta"), api("session", { token })]);
    S.meta = meta;
    S.session = session;
  } catch (error) {
    return failed(error);
  }
  S.chars = new Map(S.meta.characters.map((c) => [c.id, c]));
  S.cones = new Map(S.meta.light_cones.map((c) => [c.id, c]));
  S.relicSets = new Map(S.meta.relic_sets.map((s) => [s.id, s]));
  S.planarSets = new Map(S.meta.planar_sets.map((s) => [s.id, s]));
  S.owned = new Map(S.session.characters.filter((c) => S.chars.has(c.id)).map((c) => [c.id, c]));

  const pre = S.session.preselect || {};
  segmented($("opt-speed"), [{ value: null, label: "As built", title: "Count Speed only for characters who build it" },
    { value: true, label: "On" }, { value: false, label: "Off" }], pre.speed ?? null, (v) => { S.speed = v; });
  S.speed = pre.speed ?? null;
  S.exclude = (pre.exclude || []).filter((id) => S.owned.has(id));
  if (pre.character && S.chars.has(pre.character)) chooseMain(pre.character);
  else renderMain();
  if (pre.relic_set && S.relicSets.has(pre.relic_set)) S.sets.relic = pre.relic_set;
  if (pre.planar_set && S.planarSets.has(pre.planar_set)) S.sets.planar = pre.planar_set;
  renderSets();
  renderExclude();
  renderTeam();
  updateGo();
  sessionLine();
  setInterval(sessionLine, 60000);
  show("workspace");
}

wire();
start();
