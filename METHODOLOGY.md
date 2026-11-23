# Methodology

How OpScope turns raw match events into scouting, what each number means, how it was checked, and where it stops being reliable. The same content, shorter, is in the app's **How it works** page.

## 1. Data

- **Source:** the official GRID event feeds for the hackathon: 857 VALORANT series (VCT Americas 2025, Masters Toronto, and Game Changers 2025–2026), plus the **ability supplement**, which gives each ability cast's position and aim.
- **Scale:** 3.5 million events, 2,079 maps, 42,505 rounds, 1.4 million ability casts and 1.4 million damage and kill events.
- **Streaming:** files are read as compressed streams and never decompressed to disk. One pass per series builds six tables (`games`, `rounds`, `loadouts`, `engagements`, `casts`, `snapshots`) in about 4 minutes on 10 cores.
- **Not committed:** the tables are a local cache under the gitignored `cache/` folder.

### What the feed does and doesn't contain

| Need | Where it comes from |
|---|---|
| Who owns which gun | Every player's inventory in the full game state at the end of the buy phase (and at round end) |
| Side per round | The round segment's team sides at freeze end (the per-game summary only gives the final side) |
| Positions | Only on events: a player's position is attached when they shoot, get hit, cast, plant or defuse. There is **no continuous movement stream**, and these positions are periodic samples (±1–4 m). |
| Cast position and aim | The ability supplement, interpolated from movement samples taken 5 times a second (once a second in VCT Americas 2025). It matches 99.8% of casts. |
| Mid-round weapon pickups | Not recorded (only the spike). Inferred when a player who didn't own a gun deals damage with it. |
| Where utility lands | Not recorded. Estimated for damaging utility (section 6). |

### Data integrity

- **Rollbacks:** GRID corrects itself mid-feed with "rollback" events that undo earlier events, newest first, under new IDs. They are common: **13,255** were applied, including 87 cancelled map starts. Ignoring them left 35 maps with an extra round. The parser keeps an undo stack keyed by (event type, actor, target), and a restored map's bookkeeping rounds are flagged and excluded.
- **Validation:**
  - Every map's parsed round count equals its official score.
  - Cloud9's Operator counts match an independent raw scan.
  - Ingest is covered by synthetic-event tests (rollback then replay, side switch at round 13, buy-phase timing, supplement quality flags). Those tests were checked by breaking the parser on purpose.
- **Separate rosters:** Cloud9 (VCT Americas 2025, team 79) and Cloud9 GC (Game Changers NA 2026, team 3429) are kept as separate teams.

## 2. Reading a number

Every claim carries its sample: **"k of n rounds"**.

- **League (comparison group):** the same rate for every *other* team in the **same tier and season** (VCT 2025, Game Changers 2025, or Game Changers 2026), on the same map and side, with the same patch and event filters. Tiers and seasons are kept apart because they play on different patches and at different levels: the defense Op rate on Lotus is 10% in VCT 2025 but 17% in Game Changers. An early version compared everyone with everyone, which overstated VCT teams' differences.
- **Typical team, not pooled rounds:** the comparison rate is the **median of each other team's own rate** (teams with at least 16 rounds; at least 4 such teams, otherwise it falls back to all rounds pooled). Pooling lets one extreme team drag the rate: in the worst cases one team held 28–49% of a group's gun rounds and moved the pooled rate by 8–12 points. Across 128 weapon/map/side groups the two methods differ by a median of 2.3 points. For rarely used guns the typical team is often at 0%, which is the honest answer: most teams never do it. For Cloud9 on Lotus the result is 2 of 134 Op rounds against 8% for the typical VCT 2025 team (16% in the first, mixed-tier version).
- **95% range:** a Wilson score interval.
- **Too few to call:** percentages are hidden below 8 rounds.
- **When something is a tendency:** only when the team's 95% range does not overlap the comparison rate. The **surprise** score is the gap between them (0 if they overlap), so findings that are both unusual and well sampled rank first:

  ```
  surprise = max(0, lower95 − league, league − upper95)
  ```

- **Buy types** are by total team loadout at freeze end: eco under 6,000, full buy at 18,000 and up, and rounds 1 and 13 are pistol rounds. Win rates with and without a gun are compared **within full buys only**.

## 3. Operator profiler

- **Ownership:** the primary weapon in each player's inventory at the end of the buy phase. Operator, Odin, Outlaw and Marshal are profiled separately.
- **Survived with it:** the holder is alive at round end with the gun still in their inventory.
- **Changed hands:** someone fired the gun who didn't buy it.
- **Where it sits:** every recorded position of the holder in those rounds (when they shot, got hit or cast), shown as a density with 3 m bins and a blur, filtered by time since the buy phase. Positions are sparse: the median first sighting of an Op holder is 32 s into the round, so the map always says how many rounds it covers.
- **Setup style:** the holder's first position within 30 s, scored `d_def / (d_def + d_atk)`, where `d_def` and `d_atk` are distances to the median defender and attacker spawn. This works on three-site maps, where a single spawn-to-spawn axis would not. The team's median is ranked against every other team's setups on that map and side.
- **Kill sightlines:** each kill with the gun is drawn from shooter to victim.

## 4. Utility profiler and habits

- **Cast spot:** where the player stood when casting, from the supplement. For gap-flagged casts (usually the caster died right after), the closer movement sample is used.
- **Ability types:** every ability in the data is classed as trap, recon, smoke, stall, flash, damage, movement, heal or other.
- **Habit spots:** clustering of one player's casts of one ability on one map and side, where casts within **4 m** count as the same spot. Habits are counted in **rounds**, not casts, out of **rounds the player was on that agent**, so a rarely played agent can't look like a strong habit.
- **League baseline for habits:** the first version ranked "neT's Viper wall goes up in the same spot 70 of 71 rounds" at the top of every report. It's true but useless: across the 22 VCT 2025 Vipers with enough rounds, the typical one places that wall in the same spot in 100% of rounds, because it's a standard lineup. Now every habit is compared with the **median same-spot share of all players in the same tier and season with that ability on that map and side**, and is only listed when the player is reliably more predictable than that (same Wilson-gap rule).

## 5. Rosters

Rosters change during a season, so team tendencies can mix lineups. For each event, a team's roster is the players who played at least 20% of its rounds there (a one-map substitute doesn't count), and the **latest roster** is the one from the team's most recent event in the data. For example, NRG used three lineups across VCT Americas 2025 (FNS and Verno left during the year; brawk and skuba joined).

- Tendencies about players who aren't on the latest roster stay visible but are **marked** (e.g. "not on the roster after Stage 1 2025") and are **left out of the game plan**.
- The report states the roster and its date ("as of their last match in the data"). The data can't know about changes after that.
- Team-wide rates (Op usage, plant sites) still combine every lineup in the selected events; the report says when there's more than one, and the Event filter narrows it.

## 6. Bomb sites and named areas

- **Bomb sites:** k-means clustering of **28,952** planter positions finds 2 sites per map (3 on Haven and Lotus), each 3–7 m across.
- **Site names:** the data can't tell A from B. The community API at valorant-api.com lists every map's callouts with coordinates. Testing all 8 axis flips and swaps showed it uses **the same coordinate system as GRID**, unchanged, on all 13 maps. Each plant cluster sits 2–19 m from its "Site" callout, and the next site is 42–122 m away, so the match is unambiguous. As a sanity check, Haven's and Lotus's middle site comes out as B.
- **Area names:** any position is named after the nearest of 346 callout points within 25 m. Within 8 m of a site centre it's named after the site, because a callout is a single point and a large site's centre can be closer to a neighbouring callout. A test that compares the two sources caught exactly that ("B Boat House" for Ascent's B site). **The letter (A/B/C/Mid) is reliable; the exact area is a best guess near borders.**

## 7. Estimated landing spots (validated)

GRID doesn't record where utility lands. **Damaging** utility leaves evidence, though: the players it hurts were standing in the area.

1. **Ground truth:** pair each cast with the damage the same player later did with the same ability in that round. Each damage event goes to the most recent earlier cast, within 12 s, or 60 s for lingering utility like nanoswarms and trapwires. The victims' median position stands in for the landing. That gives **23,405** casts.
2. **Finding:** utility lands **17–24 m along the aim** (5.5 m for trapwires), while the median sideways miss is only **1.5–4.3 m**, mostly 2–3 m. So the plain cast spot is about 20 m from where it lands.
3. **Model:** per ability, the median distance along the aim in 5° bins of aim pitch, falling back to the ability's overall median when a bin has fewer than 15 casts.
4. **Validation** on 171 series held out from fitting (4,677 casts):

   | Method | Median miss |
   |---|---|
   | Cast spot | 21.3 m |
   | Fixed distance along the aim | 8.1 m |
   | **Distance by aim pitch (OpScope)** | **6.9 m** |

   The victims' spread within the damage area (roughly a 4–5 m radius) limits how small this check can go.
5. **Scope:** estimates are shown only for the 12 abilities where the model beats the cast spot: Aftershock, Blaze, Frag/ment, Hot Hands, Incendiary, Mosh Pit, Nanoswarm, Paint Shells, Razorvine, Shock Bolt, Snake Bite, Trapwire.
   - **Trapwire** improves least (12.9 m → 9.6 m), because a wire spans between two walls and can be tripped anywhere along it. The app's How it works page shows the per-ability numbers.
   - **Non-damaging utility** (smokes, alarmbots, cameras) has no damage to check against, so it stays at the cast spot with an aim arrow.
   - **Turrets** do deal damage, but at range: their victims stand a median 23 m from where the turret was placed, and the damage event's actor is Killjoy, not the turret. Their damage can't locate the turret, and since a turret is placed next to Killjoy, its cast spot is already a good position.

## 8. Game plan and predictability check

Each ranked tendency (about players still on the roster) becomes one short, rule-based suggestion that cites its evidence, at most one per map, side and category:

- **Opponent mode** is written from your side: their defense is your attack. For example, "Expect Odin spam near A Door when you attack Lotus. They bring an Odin in 47 of 117 defense rounds (typical VCT 2025 team: 11%)…"
- **Self-scout mode** (Cloud9's own teams) turns the same tendencies into what an opponent would see.

The rules are simple and readable by design. They're prompts for prep, not orders.

## 9. Limits

- Positions exist only at events, so quiet players and quiet rounds leave gaps. Every map view states how many rounds it covers.
- Landing spots are estimates, and only for damaging utility. Area names are a best guess near borders.
- Patches change agents. For example, Trapwire was reworked in patch 11.08, and the data spans patches 10.00–13.x. Use the Patch filter when comparing across a rework.
- The data is what GRID recorded for the hackathon. Some scheduled matches are missing, and 40 VALORANT series end flagged invalid by GRID; their rounds are kept, since each round still matches the official score.
