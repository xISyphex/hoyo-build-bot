// Small DOM helpers: no framework, no innerHTML with data.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(el.dataset, value);
    else el.setAttribute(key, value === true ? "" : String(value));
  }
  append(el, ...children);
  return el;
}

export function append(el, ...children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.firstChild.remove();
  return el;
}

export function $(id) {
  return document.getElementById(id);
}

function initials(name) {
  return (name || "?").replace(/[^\p{L}\p{N} ]/gu, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
}

// A square icon with a rarity rim; falls back to the name's initials when the picture can't load.
export function icon(url, name, rarity, lazy = false) {
  const box = h("span", { class: `icon${rarity ? ` r${rarity}` : ""}`, "aria-hidden": "true" });
  if (url) {
    const img = h("img", { src: url, alt: "", loading: lazy ? "lazy" : "eager", decoding: "async", referrerpolicy: "no-referrer" });
    img.addEventListener("error", () => { img.remove(); box.textContent = initials(name); }, { once: true });
    box.append(img);
  } else {
    box.textContent = initials(name);
  }
  return box;
}

export function stars(rarity) {
  return rarity ? h("span", { class: `stars r${rarity}`, "aria-label": `${rarity} stars` }, "★".repeat(rarity)) : null;
}

// A row of toggle buttons that behaves as a radio group (arrow keys move the choice).
export function segmented(container, choices, current, onChange) {
  clear(container);
  const buttons = choices.map(({ value, label, title }) => h("button", {
    type: "button", role: "radio", "aria-checked": String(value === current), tabindex: value === current ? "0" : "-1",
    title, text: label, onclick: () => select(value, true),
  }));
  function select(value, focus) {
    buttons.forEach((b, i) => {
      const on = choices[i].value === value;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
      if (on && focus) b.focus();
    });
    onChange(value);
  }
  container.onkeydown = (event) => {
    const i = buttons.indexOf(document.activeElement);
    if (i < 0) return;
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    select(choices[(i + step + choices.length) % choices.length].value, true);
  };
  if (!choices.some((c) => c.value === current) && buttons[0]) buttons[0].tabIndex = 0;
  append(container, ...buttons);
  return { set: (value) => select(value, false) };
}
