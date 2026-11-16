# Porting a definition from Fribbels

`bot/calc` computes Star Rail damage the way Fribbels' optimizer (fribbels/hsr-optimizer, MIT, see
`THIRD_PARTY_NOTICES.md`) does. A character, light cone or relic set is a small Python definition under `defs/`; its
numbers point at the game data, so a balance patch or a new ability level needs no code change.

Check a definition with `python -m bot.calc.check <id>` (characters, light cones, sets; `--eidolon N`, `--lc ID`,
`--teammate`). It prints every resolved multiplier and effect and the eidolon texts next to the eidolon effects.

## Where the numbers come from

* `P(kind, i)`: param `i` (0-based; the game text's `#1` is `i = 0`) of the ability at the level the request chose,
  eidolon bonuses included. `kind` is basic / skill / ult / talent / memo_skill / memo_talent / elation_skill. The skill
  id is `<character id><slot>` (01 Basic, 02 Skill, 03 Ultimate, 04 Talent); a reworked kit adds a leading `1`
  (`1110202`). Other ids are given with `sid`: `"{v}{id}09"` is "the enhanced Skill of this kit" (`{v}` is the rework
  prefix, `{id}` the character id), `"1{id}02"` a memosprite skill.
* `T(n, i)`: param `i` of major trace `n` (1 = A2, 2 = A4, 3 = A6). It is 0 while the trace is locked.
* `LC(i)`: param `i` of the light cone at its superimposition. The cone's always-on stats (`In the Night`'s CRIT
  Rate) come from the game data on their own; list only what the cone's conditions do.
* Set definitions list only the conditional part; the plain 2pc/4pc stats come from the game data.
* Literals: eidolon numbers (the game data carries no params for them) and Fribbels' own constants (Toughness
  reduction, Super Break thresholds). Write the literal and say where it is in a comment.

To find an index, dump the skill: `GameData(assets).skill_params("1110202", 10)`, or compare the Fribbels file's
`skill(e, 1.60, 1.76)` with the params at level 10 and 12.

## Translating Fribbels

| Fribbels | here |
|---|---|
| `defaults` / `teammateDefaults` | `Toggle(id, default=..., teammate_default=...)`, same ids |
| `x.buff(StatKey.BOOST, v)` | `Effect("dmg", v)` |
| `.damageType(DamageTag.ULT)` | `tags=Tag.ULT` |
| `.elements(ElementTag.Fire)` | `element="Fire"` |
| `.actionKind(AbilityKind.ULT)` | `actions=("ult",)` |
| `targets(TargetTag.FullTeam)` | `target="team"` |
| `targets(TargetTag.SingleTarget)` | `target="ally"` (`"ally+memo"` with its summon/memosprite) |
| `targets(TargetTag.SelfAndMemosprite)` / `Memosprite` | `target="self+memo"` / `"memo"` |
| `precomputeEffects` | `as_teammate="main_only"` when the effect would otherwise reach the team |
| `precomputeMutualEffects` | `as_teammate="mutual"` (the default) |
| `precomputeTeammateEffects` | `as_teammate="teammate_only"` |
| `UNCONVERTIBLE_*_BUFF` | `unconvertible=True` |
| `multiplicativeBoost(FINAL_DMG_BOOST)` | `Effect("final", v)` |
| `dynamicConditionals` on a stat threshold | `when=StatAtLeast("ehr", 0.75)` |
| `dynamicStatConversion` | `Scale(src, ratio, above=..., step=..., cap=...)` |
| `HitDefinitionBuilder.standardX().atkScaling(s).toughnessDmg(t)` | `Hit("crit", Tag.X, atk=s, toughness=t)` |
| `.sourceEntity(memo).scalingEntity(owner)` | `Hit(..., entity="memo", scale="self")` |
| `standardDot().tickCoefficient(n)` | `Hit("dot", Tag.DOT, tick=n)` |
| `standardSuperBreak().referenceHit(h)` | `Hit("super_break", Tag.SUPER_BREAK, toughness=<h's>)` |
| `linearBuff()` / `discreteBuff()` | `Hit("buff", Tag.NONE, src=..., ratio=..., flat=...)` / `above, step, per, cap` |
| `comboTurnAbilities` | `rotation=[...]` without the leading NULL; START_/END_/WHOLE_ prefixes dropped |
| `initializeConfigurations: enemyWeaknessBroken = true` | `broken_when=On(...)` |
| `ashblazingMulti([single(a), aoe(b), ...])` | `Ability(..., ashblazing=[AshHit("single", a), AshHit("aoe", b)])` |

Conditions: `Eidolon(n)`, `Trace(n)`, `On(toggle)`, `TogAtLeast`, `TeamPath(path, n)`, `SamePath(n)`,
`SameElement()`, `MainHasMemo()`, `OwnerIs(id)`, `Broken()`, combined with `&`, `|`, `~`.

A supporter that speeds the main character up (Bronya, Sunday) sets `advance` (extra turns per turn of the carry).
A supporter scored as the main character has a rotation of one `"buff"` ability: Fribbels' support score.

## Reworked kits

Fribbels keeps the old kit as `<Name>.ts` and the rework as `<Name>B1.ts`. Port the B1 file with id
`"<id>b1"`; the engine picks it when the game data has the rework's skill ids. Eidolon numbers of B1 kits come from
the Fribbels file: the game data's eidolon text is still the old kit's.

## What the fallback does

Characters, light cones and sets without a definition are read from their game text (`bot/kit.py`,
`bot/cone_effects.py`): the strongest hit of each ability and the buffs the text states plainly. Results that use the
fallback are marked `approximate`, and undefined teammates add nothing. Write a definition to replace it.

## Header

Every ported file starts with

```
# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# <path of the Fribbels file>, branch main as of <date>. Numbers re-pointed to game data params.
```

Do not port characters that are not released yet.
