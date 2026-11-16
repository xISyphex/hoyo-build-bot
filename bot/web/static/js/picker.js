// One searchable picker dialog shared by every chooser on the page (characters, light cones, sets).
// Keyboard: type to filter, Up/Down to move, Enter to pick, Escape to close; focus goes back to the trigger.

import { $, append, clear, h, icon, stars } from "./dom.js";

const dialog = $("picker");
const title = $("picker-title");
const search = $("picker-search");
const list = $("picker-list");
const filtersBox = $("picker-filters");
let state = null;

function normalize(text) {
  return (text || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]/g, "");
}

function visible() {
  const words = normalize(search.value).split(/\s+/).filter(Boolean);
  const filter = state.filters[state.filter];
  return state.options.filter((o) => {
    if (filter && filter.test && o.id !== null && !filter.test(o)) return false;
    const hay = normalize(`${o.name} ${o.sub || ""} ${(o.tags || []).join(" ")} ${o.search || ""}`);
    return words.every((w) => hay.includes(w));
  });
}

function render() {
  clear(list);
  state.shown = visible();
  if (!state.shown.length) {
    list.append(h("li", { class: "none", role: "presentation", text: "Nothing matches." }));
    search.removeAttribute("aria-activedescendant");
    return;
  }
  state.active = Math.min(Math.max(state.active, 0), state.shown.length - 1);
  state.shown.forEach((o, i) => {
    const li = h("li", {
      id: `opt-${i}`, role: "option", "aria-selected": String(i === state.active),
      class: `${o.rarity ? `r${o.rarity}` : ""}${o.id === state.current ? " current" : ""}`,
      onclick: () => pick(o), onmousemove: () => { if (state.active !== i) { state.active = i; mark(); } },
    },
    o.id === null ? null : icon(o.icon, o.name, o.rarity, true),
    h("span", { class: "opt-text" },
      h("span", { class: "opt-name" }, o.name, ...(o.tags || []).map((t) => h("span", { class: `tag${t === "Owned" ? " gold" : ""}`, text: t }))),
      o.sub ? h("span", { class: "opt-sub", text: o.sub }) : null));
    list.append(li);
  });
  mark();
}

function mark() {
  [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === state.active)));
  const li = list.children[state.active];
  if (li && li.id) {
    search.setAttribute("aria-activedescendant", li.id);
    li.scrollIntoView({ block: "nearest" });
  }
}

function pick(option) {
  const done = state.onPick;
  close();
  done(option.id, option);
}

function close() {
  if (dialog.open) dialog.close();
}

dialog.addEventListener("close", () => {
  if (!state || dialog.open) return;  // a pick already opened the next picker
  const back = state.trigger;
  state = null;
  if (back && back.isConnected) back.focus();
});
$("picker-close").addEventListener("click", close);
dialog.addEventListener("click", (event) => { if (event.target === dialog) close(); });  // the backdrop
search.addEventListener("input", () => { state.active = 0; render(); });
search.addEventListener("keydown", (event) => {
  if (!state) return;
  const columns = Math.max(1, Math.round(list.clientWidth / ((list.children[0] && list.children[0].offsetWidth) || list.clientWidth)));
  const moves = { ArrowDown: columns, ArrowUp: -columns, PageDown: 8 * columns, PageUp: -8 * columns };
  if (event.key in moves) {
    event.preventDefault();
    state.active = Math.min(Math.max(state.active + moves[event.key], 0), state.shown.length - 1);
    mark();
  } else if (event.key === "Enter") {
    event.preventDefault();
    if (state.shown[state.active]) pick(state.shown[state.active]);
  }
});

// options: [{id, name, icon, rarity, sub, tags, search}]; id null is the "none" choice.
// filters: [{label, test}] shown as toggles above the list (the first is selected).
export function openPicker({ trigger, heading, options, current = null, filters = [], onPick, placeholder = "Search" }) {
  state = { trigger, options, current, filters, filter: 0, onPick, active: 0, shown: [] };
  title.textContent = heading;
  search.value = "";
  search.placeholder = placeholder;
  clear(filtersBox);
  filters.forEach((f, i) => filtersBox.append(h("button", {
    type: "button", "aria-pressed": String(i === 0), text: f.label,
    onclick: (event) => {
      state.filter = i;
      [...filtersBox.children].forEach((b) => b.setAttribute("aria-pressed", String(b === event.currentTarget)));
      state.active = 0;
      render();
    },
  })));
  const at = options.findIndex((o) => o.id === current);
  state.active = at < 0 ? 0 : at;
  render();
  dialog.showModal();
  search.focus();
}

// Draws a trigger button's face for the chosen option.
export function showChoice(trigger, option, emptyText) {
  clear(trigger);
  trigger.classList.remove("r3", "r4", "r5");
  if (!option || option.id === null) {
    append(trigger, h("span", { class: "pt-empty", text: (option && option.name) || emptyText }));
    trigger.setAttribute("aria-label", `${trigger.dataset.what || "Choice"}: ${(option && option.name) || emptyText}. Change`);
    return;
  }
  if (option.rarity) trigger.classList.add(`r${option.rarity}`);
  append(trigger, icon(option.icon, option.name, option.rarity),
    h("span", { class: "pt-text" },
      h("span", { class: "pt-name" }, option.name, option.owned ? h("span", { class: "tag gold", text: "Owned" }) : null),
      option.sub ? h("span", { class: "pt-sub" }, stars(option.rarity), option.rarity ? " " : "", option.sub) : null));
  trigger.setAttribute("aria-label", `${trigger.dataset.what || "Choice"}: ${option.name}. Change`);
}
