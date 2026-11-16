// The result panel: the six chosen relics, the final stats and the score.

import { clear, h, icon } from "./dom.js";

const FIELD_NAMES = {
  "character.level": "level", "character.ascension": "ascension", "character.eidolon": "eidolons",
  "character.abilities": "ability levels", "character.traces": "traces", "character.light_cone": "chosen light cone",
  teammates: "team",
};

function relicCard(relic, mainId) {
  const moved = relic.owner !== mainId;
  return h("li", { class: `relic r${relic.rarity}` },
    h("div", { class: "relic-top" },
      icon(relic.icon, relic.set_name, relic.rarity),
      h("div", {},
        h("div", { class: "relic-slot", text: relic.slot }),
        h("div", { class: "relic-main" }, relic.main.name, " ", h("span", { text: relic.main.value })))),
    h("ul", { class: "relic-subs", "aria-label": "Substats" }, relic.subs.map((s) => h("li", {},
      h("span", {}, s.name, s.rolls > 1 ? h("span", { class: "rolls", title: `${s.rolls} rolls`, text: `×${s.rolls}` }) : null),
      h("span", { class: "v", text: s.value })))),
    h("div", { class: `relic-owner${moved ? " moved" : ""}`, title: relic.set_name },
      moved ? `From ${relic.owner_name}` : "Already theirs", " · ", relic.set_name));
}

function counted(statName, names) {
  return names.some((c) => statName === c || statName.startsWith(`${c} `) || (c.endsWith(" DMG") && statName === `${c} Boost`));
}

export function showBusy(body) {
  clear(body).append(h("div", { class: "busy", role: "status" }, h("div", { class: "spinner", "aria-hidden": "true" }),
    "Trying every combination of your relics…"));
}

export function showError(body, message, details) {
  const box = h("div", { class: "alert", role: "alert" }, message);
  if (details && details.length) box.append(h("ul", {}, details.map((d) => h("li", {}, `${d.field}: ${d.message}`))));
  clear(body).append(box);
}

export function showResult(body, result, character) {
  clear(body);
  const gain = result.score_gain;
  const gainText = gain === null || gain === undefined ? "Nothing worn now to compare with"
    : Math.abs(gain) < 0.05 ? "The same as what they wear now" : `${gain > 0 ? "+" : ""}${gain.toFixed(1)}% vs. what they wear now`;
  body.append(
    h("div", { class: "result-head" },
      h("div", { class: "result-who" },
        icon(character && character.icon, result.character.name, character && character.rarity),
        h("div", {},
          h("h3", { text: result.character.name }),
          h("p", { text: `4pc ${result.relic_set.name} · 2pc ${result.planar_set.name}` }))),
      h("div", { class: "score" },
        h("span", { class: "label", text: "Damage index" }),
        h("span", { class: "num", text: Math.round(result.score).toLocaleString("en-US") }),
        h("span", { class: `gain ${gain > 0.05 ? "up" : "same"}`, text: gainText }))),
  );
  if (result.light_cone) {
    const lc = result.light_cone;
    body.append(h("div", { class: "result-cone" },
      h("div", {}, h("b", { text: lc.name }),
        h("span", { text: `Lv. ${lc.level} · S${lc.rank}${lc.owner_name && lc.owner_name !== result.character.name ? ` · from ${lc.owner_name}` : ""}` }))));
  }
  body.append(h("ul", { class: "relics", "aria-label": "Chosen relics" }, result.relics.map((r) => relicCard(r, result.character.id))));
  body.append(h("table", { class: "stats" },
    h("caption", { class: "label", text: "Final stats" }),
    h("tbody", {}, result.stats.map((s) => h("tr", { class: counted(s.name, result.counted) ? "counted" : "" },
      h("th", { scope: "row", text: s.name }), h("td", { text: s.value }))))));
  body.append(h("p", { class: "result-note" },
    h("strong", { text: "Scored on " }), result.counted.join(", "), `. ${result.tried.toLocaleString("en-US")} combinations tried.`));
  if (result.ignored && result.ignored.length) {
    const names = [...new Set(result.ignored.map((f) => FIELD_NAMES[f] || f))];
    body.append(h("p", { class: "result-note" }, h("strong", { text: "Not used by the current scoring yet: " }), names.join(", "), "."));
  }
  if (result.assumed) body.append(h("p", { class: "result-note", text: result.assumed }));
}
