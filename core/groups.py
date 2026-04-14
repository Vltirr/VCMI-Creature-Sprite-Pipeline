import re

CREATURE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

VALID_GROUPS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 30, 31, 32, 40, 41, 42, 50, 51]

GROUP_NAMES = {
    0: "(Basic)Movement",
    1: "(Basic)Mouse over",
    2: "(Basic)Idle",
    3: "(Basic)Hitted",
    4: "(Basic)Defence",
    5: "(Basic)Death",
    6: "(Basic)Death (ranged)",
    7: "(Rotation)Turn left",
    8: "(Rotation)Turn right",
    11: "(Melee)Attack (up)",
    12: "(Melee)Attack (front)",
    13: "(Melee)Attack (down)",
    14: "(Ranged)Shooting (up)",
    15: "(Ranged)Shooting (front)",
    16: "(Ranged)Shooting (down)",
    17: "(Special)Special (up)",
    18: "(Special)Special (front)",
    19: "(Special)Special (down)",
    20: "Movement start",
    21: "Movement end",
    22: "Dead",
    23: "Dead (ranged)",
    24: "Resurrection",
    30: "(Spellcast)Cast (up)",
    31: "(Spellcast)Cast (front)",
    32: "(Spellcast)Cast (down)",
    40: "(Group)Group Attack (up)",
    41: "(Group)Group Attack (front)",
    42: "(Group)Group Attack (down)",
    50: "Teleportation start",
    51: "Teleportation end",
}


def group_label(gid: int) -> str:
    return f"{gid} - {GROUP_NAMES.get(gid, 'Unknown')}"

