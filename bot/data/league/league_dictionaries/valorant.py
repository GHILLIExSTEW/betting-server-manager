# League Data/data/league/league_dictionaries/valorant.py
"""
Valorant (VCT) Team names and abbreviations for major regions.
"""

# Maps lowercase full team name to a common abbreviation
VALORANT_ABBREVIATIONS = {
    # VCT Americas
    "g2 esports": "G2",
    "sentinels": "SEN",
    "cloud9": "C9",
    "evil geniuses": "EG",
    "krü esports": "KRU",
    "kru esports": "KRU", # Alt spelling
    "mibr": "MIBR",
    "loud": "LOUD", # Often used directly
    "furia esports": "FUR",
    "100 thieves": "100T",
    "leviatán": "LEV",
    "leviatan": "LEV", # Alt spelling
    "nrg esports": "NRG",
    "2game esports": "2G",

    # VCT EMEA
    "team vitality": "VIT",
    "team liquid": "TL",
    "team heretics": "TH",
    "fut esports": "FUT",
    "fnatic": "FNC",
    "bbl esports": "BBL",
    "giantx": "GX",
    "gentle mates": "M8",
    "movistar koi": "KOI",
    "natus vincere": "NAVI",
    "karmine corp": "KC",
    "apeks": "APK",

    # VCT Pacific
    "drx": "DRX", # Often used directly
    "t1": "T1", # Valorant branch
    "gen.g": "GENG", # Or GEN
    "gen.g esports": "GENG",
    "talon esports": "TLN",
    "nongshim redforce": "NS",
    "detonation focusme": "DFM",
    "rex regum qeon": "RRQ",
    "paper rex": "PRX",
    "boom esports": "BME", # Or BOOM
    "team secret": "TS",
    "global esports": "GE",
    "zeta division": "ZETA",

    # VCT China
    "edward gaming": "EDG",
    "trace esports": "TE",
    "bilibili gaming": "BLG",
    "dragon ranger gaming": "DRG",
    "funplus phoenix": "FPX", # Valorant branch
    "xi lai gaming": "XLG",
    "nova esports": "NOVA",
    "jd gaming": "JDG", # Valorant branch
    "wolves esports": "WOL",
    "tyloo": "TYL", # Valorant branch
    "titan esports club": "TEC",
    "all gamers": "AG",

    # Add other relevant teams as needed
}

# Maps lowercase abbreviations, common names, and full names to the Standardized Team Name
TEAM_FULL_NAMES = {
    # VCT Americas
    "g2": "G2 Esports",
    "g2 esports": "G2 Esports",
    "sen": "Sentinels",
    "sentinels": "Sentinels",
    "c9": "Cloud9",
    "cloud9": "Cloud9",
    "eg": "Evil Geniuses",
    "evil geniuses": "Evil Geniuses",
    "kru": "KRÜ Esports",
    "krü": "KRÜ Esports", # Alt spelling
    "kru esports": "KRÜ Esports",
    "krü esports": "KRÜ Esports", # Alt spelling
    "mibr": "MIBR",
    "made in brazil": "MIBR", # Full name if needed
    "loud": "LOUD",
    "lll": "LOUD", # Meme/old abbreviation sometimes seen
    "fur": "FURIA Esports",
    "furia": "FURIA Esports",
    "furia esports": "FURIA Esports",
    "100": "100 Thieves",
    "100t": "100 Thieves",
    "100 thieves": "100 Thieves",
    "lev": "Leviatán",
    "leviatan": "Leviatán",
    "leviatán": "Leviatán", # Alt spelling
    "nrg": "NRG Esports",
    "nrg esports": "NRG Esports",
    "2g": "2Game Esports",
    "2game": "2Game Esports",
    "2game esports": "2Game Esports",

    # VCT EMEA
    "vit": "Team Vitality",
    "vitality": "Team Vitality",
    "team vitality": "Team Vitality",
    "tl": "Team Liquid",
    "liquid": "Team Liquid",
    "team liquid": "Team Liquid",
    "th": "Team Heretics",
    "heretics": "Team Heretics",
    "team heretics": "Team Heretics",
    "fut": "FUT Esports",
    "fut esports": "FUT Esports",
    "fnc": "Fnatic",
    "fnatic": "Fnatic",
    "bbl": "BBL Esports",
    "bbl esports": "BBL Esports",
    "gx": "GIANTX",
    "giantx": "GIANTX",
    "m8": "Gentle Mates",
    "gentle mates": "Gentle Mates",
    "koi": "Movistar KOI",
    "movistar koi": "Movistar KOI",
    "navi": "Natus Vincere",
    "natus vincere": "Natus Vincere",
    "kc": "Karmine Corp",
    "karmine": "Karmine Corp",
    "karmine corp": "Karmine Corp",
    "apk": "Apeks",
    "apeks": "Apeks",

    # VCT Pacific
    "drx": "DRX",
    "t1": "T1", # Valorant branch
    "gen": "Gen.G", # Common abbreviation
    "geng": "Gen.G",
    "gen g": "Gen.G",
    "gen.g": "Gen.G",
    "gen.g esports": "Gen.G",
    "tln": "TALON Esports",
    "talon": "TALON Esports",
    "talon esports": "TALON Esports",
    "ns": "Nongshim RedForce",
    "nongshim": "Nongshim RedForce", # Valorant branch
    "nongshim redforce": "Nongshim RedForce",
    "dfm": "DetonatioN FocusMe",
    "detonation focusme": "DetonatioN FocusMe",
    "rrq": "Rex Regum Qeon",
    "rex regum qeon": "Rex Regum Qeon",
    "prx": "Paper Rex",
    "paper rex": "Paper Rex",
    "bme": "BOOM Esports",
    "boom": "BOOM Esports",
    "boom esports": "BOOM Esports",
    "ts": "Team Secret",
    "secret": "Team Secret",
    "team secret": "Team Secret",
    "ge": "Global Esports",
    "global esports": "Global Esports",
    "zeta": "ZETA DIVISION",
    "zeta division": "ZETA DIVISION",

    # VCT China
    "edg": "EDward Gaming",
    "edward gaming": "EDward Gaming",
    "te": "Trace Esports",
    "trace": "Trace Esports",
    "trace esports": "Trace Esports",
    "blg": "Bilibili Gaming",
    "bilibili": "Bilibili Gaming", # Valorant branch
    "bilibili gaming": "Bilibili Gaming",
    "drg": "Dragon Ranger Gaming",
    "dragon ranger": "Dragon Ranger Gaming",
    "dragon ranger gaming": "Dragon Ranger Gaming",
    "fpx": "FunPlus Phoenix", # Valorant branch
    "funplus": "FunPlus Phoenix",
    "funplus phoenix": "FunPlus Phoenix",
    "xlg": "Xi Lai Gaming",
    "xi lai": "Xi Lai Gaming",
    "xi lai gaming": "Xi Lai Gaming",
    "nova": "Nova Esports",
    "nova esports": "Nova Esports",
    "jdg": "JD Gaming", # Valorant branch
    "jd gaming": "JD Gaming",
    "wol": "Wolves Esports",
    "wolves": "Wolves Esports",
    "wolves esports": "Wolves Esports",
    "tyl": "TYLOO", # Valorant branch
    "tyloo": "TYLOO",
    "tec": "Titan Esports Club",
    "titan esports": "Titan Esports Club",
    "titan esports club": "Titan Esports Club",
    "ag": "All Gamers",
    "all gamers": "All Gamers",

    # Add other teams as needed
}