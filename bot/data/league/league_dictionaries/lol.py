# League Data/data/league/league_dictionaries/lol.py
"""
League of Legends (LoL) Team names and abbreviations for major regions.
"""

# Maps lowercase full team name to a common abbreviation
LOL_ABBREVIATIONS = {
    # LCK (Korea)
    "hanwha life esports": "HLE",
    "t1": "T1",
    "gen.g": "GEN",
    "dplus kia": "DK",
    "kt rolster": "KT",
    "bnk fearx": "FOX",
    "drx": "DRX",
    "oksavingsbank brion": "BRO",
    "dn freecs": "DN", # Formerly KDF
    "kwangdong freecs": "DN", # Alias
    "nongshim redforce": "NS",

    # LPL (China)
    "top esports": "TES",
    "anyone's legend": "AL",
    "jd gaming": "JDG",
    "weibo gaming": "WBG",
    "tt gaming": "TT",
    "bilibili gaming": "BLG",
    "ninjas in pyjamas": "NIP", # LPL Branch
    "invictus gaming": "IG",
    "lgd gaming": "LGD",
    "oh my god": "OMG",
    "edward gaming": "EDG",
    "royal never give up": "RNG",
    "funplus phoenix": "FPX",
    "team we": "WE",
    "ultra prime": "UP",
    "lng esports": "LNG",

    # LEC (EMEA)
    "fnatic": "FNC",
    "karmine corp": "KC",
    "g2 esports": "G2", # LEC Branch
    "movistar koi": "KOI", # Formerly MAD Lions KOI
    "mad lions koi": "KOI", # Alias
    "team vitality": "VIT", # LEC Branch
    "giantx": "GX",
    "team bds": "BDS",
    "team heretics": "TH",
    "sk gaming": "SK",
    "rogue": "RGE",

    # LTA North (Americas North / formerly LCS)
    "cloud9": "C9",
    "team liquid": "TL", # LTA Branch
    "dignitas": "DIG",
    "flyquest": "FLY",
    "shopify rebellion": "SR",
    "lyon gaming": "LYN",
    "100 thieves": "100T", # Or 100
    "disguised": "DSG",

    # Add other regions/teams as needed (LTA South, LCP, VCS, etc.)
}

# Maps lowercase abbreviations, common names, and full names to the Standardized Team Name
TEAM_FULL_NAMES = {
    # LCK
    "hle": "Hanwha Life Esports",
    "hanwha life": "Hanwha Life Esports",
    "hanwha life esports": "Hanwha Life Esports",
    "t1": "T1",
    "gen": "Gen.G",
    "geng": "Gen.G",
    "gen g": "Gen.G",
    "gen.g": "Gen.G",
    "dk": "Dplus KIA",
    "dplus": "Dplus KIA",
    "dplus kia": "Dplus KIA",
    "damwon": "Dplus KIA", # Former name
    "damwon kia": "Dplus KIA", # Former name
    "kt": "KT Rolster",
    "kt rolster": "KT Rolster",
    "fox": "BNK FearX",
    "fearx": "BNK FearX",
    "bnk fearx": "BNK FearX",
    "fredit brion": "OKSavingsBank Brion", # Former name
    "brion": "OKSavingsBank Brion",
    "oksavingsbank brion": "OKSavingsBank Brion",
    "bro": "OKSavingsBank Brion",
    "drx": "DRX",
    "dn": "DN Freecs",
    "dn freecs": "DN Freecs",
    "kdf": "DN Freecs", # Former abbreviation
    "kwangdong": "DN Freecs",
    "kwangdong freecs": "DN Freecs",
    "ns": "Nongshim RedForce",
    "nongshim": "Nongshim RedForce",
    "nongshim redforce": "Nongshim RedForce",

    # LPL
    "tes": "Top Esports",
    "top esports": "Top Esports",
    "al": "Anyone's Legend",
    "anyone's legend": "Anyone's Legend",
    "jdg": "JD Gaming",
    "jd gaming": "JD Gaming",
    "wbg": "Weibo Gaming",
    "weibo": "Weibo Gaming",
    "weibo gaming": "Weibo Gaming",
    "tt": "TT Gaming",
    "tt gaming": "TT Gaming",
    "blg": "Bilibili Gaming",
    "bilibili": "Bilibili Gaming",
    "bilibili gaming": "Bilibili Gaming",
    "nip": "Ninjas in Pyjamas", # LPL branch
    "ig": "Invictus Gaming",
    "invictus": "Invictus Gaming",
    "invictus gaming": "Invictus Gaming",
    "lgd": "LGD Gaming",
    "lgd gaming": "LGD Gaming",
    "omg": "Oh My God",
    "oh my god": "Oh My God",
    "edg": "EDward Gaming",
    "edward gaming": "EDward Gaming",
    "rng": "Royal Never Give Up",
    "royal never give up": "Royal Never Give Up",
    "fpx": "FunPlus Phoenix",
    "funplus": "FunPlus Phoenix",
    "funplus phoenix": "FunPlus Phoenix",
    "we": "Team WE",
    "team we": "Team WE",
    "up": "Ultra Prime",
    "ultra prime": "Ultra Prime",
    "lng": "LNG Esports",
    "lng esports": "LNG Esports",
    "li ning": "LNG Esports", # Sponsor name often used

    # LEC
    "fnc": "Fnatic",
    "fnatic": "Fnatic",
    "kc": "Karmine Corp",
    "karmine": "Karmine Corp",
    "karmine corp": "Karmine Corp",
    "g2": "G2 Esports", # LEC branch
    "g2 esports": "G2 Esports",
    "koi": "Movistar KOI",
    "movistar koi": "Movistar KOI",
    "mad lions koi": "Movistar KOI", # Former name
    "mad": "Movistar KOI", # Former abbreviation
    "vit": "Team Vitality", # LEC branch
    "vitality": "Team Vitality",
    "team vitality": "Team Vitality",
    "gx": "GIANTX",
    "giantx": "GIANTX",
    "bds": "Team BDS",
    "team bds": "Team BDS",
    "th": "Team Heretics",
    "heretics": "Team Heretics",
    "team heretics": "Team Heretics",
    "sk": "SK Gaming",
    "sk gaming": "SK Gaming",
    "rge": "Rogue",
    "rogue": "Rogue",

    # LTA North / LCS
    "c9": "Cloud9",
    "cloud9": "Cloud9",
    "tl": "Team Liquid", # LTA branch
    "liquid": "Team Liquid",
    "team liquid": "Team Liquid",
    "dig": "Dignitas",
    "dignitas": "Dignitas",
    "fly": "FlyQuest",
    "flyquest": "FlyQuest",
    "sr": "Shopify Rebellion",
    "shopify": "Shopify Rebellion",
    "shopify rebellion": "Shopify Rebellion",
    "lyn": "Lyon Gaming",
    "lyon": "Lyon Gaming",
    "lyon gaming": "Lyon Gaming",
    "100": "100 Thieves",
    "100t": "100 Thieves",
    "100 thieves": "100 Thieves",
    "dsg": "Disguised",
    "disguised": "Disguised",
    "disguised toast": "Disguised", # Creator's name often used

    # Add other teams as needed...
}