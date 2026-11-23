"""Weapon and ability groupings used across ingest and analytics.

Ability classes are assigned at load time (not baked into the cache), so editing this file
never requires rebuilding the cache.
"""

# Primary weapons, ordered so the first match in an inventory is the player's main gun.
PRIMARY_WEAPONS = [
    "operator", "odin", "outlaw", "marshal", "ares",          # snipers + LMGs first: they define a role
    "vandal", "phantom", "guardian", "bulldog",                # rifles
    "spectre", "stinger", "judge", "bucky",                    # SMGs + shotguns
]
SIDEARMS = ["sheriff", "ghost", "bandit", "frenzy", "shorty", "classic"]
SHIELDS = {"heavyshield": "heavy", "lightshield": "light"}

WEAPON_GROUP = {
    "operator": "operator",
    "odin": "odin",
    "outlaw": "sniper", "marshal": "sniper",
    "ares": "lmg",
    "vandal": "rifle", "phantom": "rifle", "guardian": "rifle", "bulldog": "rifle",
    "spectre": "smg", "stinger": "smg",
    "judge": "shotgun", "bucky": "shotgun",
    **{w: "sidearm" for w in SIDEARMS},
    "melee": "melee", "knife": "melee",
}

# The "big gun" family the Operator profiler tracks.
SCOUTED_WEAPONS = ("operator", "odin", "outlaw", "marshal")

_PRIMARY_RANK = {w: i for i, w in enumerate(PRIMARY_WEAPONS)}
_SIDEARM_RANK = {w: i for i, w in enumerate(SIDEARMS)}


def primary_weapon(item_ids: list[str]) -> str | None:
    """Pick the player's main gun from inventory item ids (None if no primary)."""
    best = min((i for i in item_ids if i in _PRIMARY_RANK), key=_PRIMARY_RANK.__getitem__, default=None)
    return best


def sidearm(item_ids: list[str]) -> str | None:
    return min((i for i in item_ids if i in _SIDEARM_RANK), key=_SIDEARM_RANK.__getitem__, default=None)


def shield(item_ids: list[str]) -> str | None:
    return next((SHIELDS[i] for i in item_ids if i in SHIELDS), None)


# Utility classes, in coach priority order (see CLAUDE.md).
UTIL_CLASSES = ["trap", "recon", "smoke", "stall", "flash", "damage", "movement", "heal", "other"]

# ability id -> util class, covering every ability id in the corpus (grouped by agent).
# "trap" = placeable info/denial utility that sits on the map (the top scouting priority).
_CLASSES_BY_AGENT = {
    "astra":     {"stars": "smoke", "nebula-dissipate": "smoke", "nova-pulse": "stall", "gravity-well": "stall"},
    "breach":    {"fault-line": "stall", "flashpoint": "flash", "aftershock": "damage", "rolling-thunder": "stall"},
    "brimstone": {"sky-smoke": "smoke", "stim-beacon": "other", "incendiary": "stall", "orbital-strike": "damage"},
    "chamber":   {"trademark": "trap", "rendezvous": "movement", "headhunter": "other", "tour-de-force": "other"},
    "clove":     {"ruse": "smoke", "meddle": "stall", "pick-me-up": "other", "not-dead-yet": "other"},
    "cypher":    {"trapwire": "trap", "cyber-cage": "smoke", "spycam": "recon", "neural-theft": "recon"},
    "deadlock":  {"sonic-sensor": "trap", "gravnet": "stall", "barrier-mesh": "stall", "annihilation": "damage"},
    "fade":      {"prowler": "recon", "haunt": "recon", "seize": "stall", "nightfall": "recon"},
    "gekko":     {"dizzy": "flash", "wingman": "stall", "mosh-pit": "stall", "thrash": "stall"},
    "harbor":    {"high-tide": "smoke", "cove": "smoke", "cascade": "smoke", "storm-surge": "stall", "reckoning": "stall"},
    "iso":       {"undercut": "stall", "contingency": "smoke", "double-tap": "other", "kill-contract": "other"},
    "jett":      {"cloudburst": "smoke", "tailwind": "movement", "updraft": "movement"},
    "kay/o":     {"zero-point": "recon", "flash-drive": "flash", "frag-ment": "damage", "null-cmd": "stall"},
    "killjoy":   {"alarmbot": "trap", "turret": "trap", "nanoswarm": "trap", "lockdown": "stall"},
    "neon":      {"fast-lane": "smoke", "relay-bolt": "stall", "high-gear": "movement"},
    "omen":      {"dark-cover": "smoke", "paranoia": "flash", "shrouded-step": "movement", "from-the-shadows": "movement"},
    "phoenix":   {"curveball": "flash", "blaze": "smoke", "hot-hands": "stall"},
    "raze":      {"boom-bot": "damage", "paint-shells": "damage", "showstopper": "damage", "blast-pack": "movement"},
    "reyna":     {"leer": "flash", "devour": "heal"},
    "sage":      {"slow-orb": "stall", "barrier-orb": "stall", "healing-orb": "heal", "resurrection": "heal"},
    "skye":      {"guiding-light": "flash", "trailblazer": "recon", "seekers": "recon", "regrowth": "heal"},
    "sova":      {"recon-bolt": "recon", "owl-drone": "recon", "shock-bolt": "damage", "hunter's-fury": "damage"},
    "tejo":      {"stealth-drone": "recon", "special-delivery": "stall", "guided-salvo": "damage", "armageddon": "damage"},
    "veto":      {"chokehold": "trap", "crosscut": "movement", "interceptor": "other"},
    "viper":     {"toxic-screen": "smoke", "poison-cloud": "smoke", "viper's-pit": "smoke", "snake-bite": "stall"},
    "vyse":      {"razorvine": "trap", "shear": "trap", "arc-rose": "flash", "steel-garden": "stall"},
    "waylay":    {"saturate": "stall", "convergent-paths": "stall", "refract": "movement", "light-speed": "movement"},
    "yoru":      {"blindside": "flash", "gatecrash": "movement", "dimensional-drift": "movement", "fakeout": "other"},
    # Miks (controller, Mar 2026): Waveform = map-targeted smokes; M-Pulse = concuss/heal throwable;
    # Harmonize = combat stim (like Brimstone's beacon); Bassquake = knockback/deafen/slow ultimate.
    "miks":      {"waveform": "smoke", "m-pulse": "stall", "harmonize": "other", "bassquake": "stall"},
}
ABILITY_CLASS: dict[str, str] = {a: c for kit in _CLASSES_BY_AGENT.values() for a, c in kit.items()}
ABILITY_AGENT: dict[str, str] = {a: agent for agent, kit in _CLASSES_BY_AGENT.items() for a in kit}


def util_class(ability_id: str | None) -> str:
    return ABILITY_CLASS.get(ability_id or "", "other")
