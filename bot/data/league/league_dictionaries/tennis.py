# bot/data/league/league_dictionaries/tennis.py
"""
ATP and WTA Tennis Player names and aliases.
"""

TENNIS_PLAYERS = {
    # === ATP Players (Examples based on recent rankings/prominence) ===
    "djokovic": "Novak Djokovic",
    "novak djokovic": "Novak Djokovic",
    "nole": "Novak Djokovic",
    "nd": "Novak Djokovic",

    "alcaraz": "Carlos Alcaraz",
    "carlos alcaraz": "Carlos Alcaraz",
    "ca": "Carlos Alcaraz",

    "sinner": "Jannik Sinner",
    "jannik sinner": "Jannik Sinner",
    "js": "Jannik Sinner", # Note: JS could conflict with Jordan Spieth if used globally

    "medvedev": "Daniil Medvedev",
    "daniil medvedev": "Daniil Medvedev",
    "dm": "Daniil Medvedev",

    "rublev": "Andrey Rublev",
    "andrey rublev": "Andrey Rublev",
    "ar": "Andrey Rublev",

    "zverev": "Alexander Zverev",
    "alexander zverev": "Alexander Zverev",
    "sascha": "Alexander Zverev",
    "az": "Alexander Zverev",

    "tsitsipas": "Stefanos Tsitsipas",
    "stefanos tsitsipas": "Stefanos Tsitsipas",
    "st": "Stefanos Tsitsipas", # Note: ST could conflict

    "ruud": "Casper Ruud",
    "casper ruud": "Casper Ruud",
    "cr": "Casper Ruud",

    "fritz": "Taylor Fritz",
    "taylor fritz": "Taylor Fritz",
    "tf": "Taylor Fritz",

    "rune": "Holger Rune",
    "holger rune": "Holger Rune",
    "hr": "Holger Rune",

    "nadal": "Rafael Nadal",
    "rafael nadal": "Rafael Nadal",
    "rafa": "Rafael Nadal",
    "rn": "Rafael Nadal", # Less common abbreviation

    "federer": "Roger Federer", # Often included despite retirement
    "roger federer": "Roger Federer",
    "rf": "Roger Federer",

    # === WTA Players (Examples based on recent rankings/prominence) ===
    "swiatek": "Iga Świątek",
    "iga świątek": "Iga Świątek",
    "iga swiatek": "Iga Świątek", # Common spelling without diacritic
    "is": "Iga Świątek",

    "sabalenka": "Aryna Sabalenka",
    "aryna sabalenka": "Aryna Sabalenka",
    "as": "Aryna Sabalenka",

    "rybakina": "Elena Rybakina",
    "elena rybakina": "Elena Rybakina",
    "er": "Elena Rybakina",

    "gauff": "Coco Gauff",
    "coco gauff": "Coco Gauff",
    "cg": "Coco Gauff",

    "pegula": "Jessica Pegula",
    "jessica pegula": "Jessica Pegula",
    "jp": "Jessica Pegula",

    "jabeur": "Ons Jabeur",
    "ons jabeur": "Ons Jabeur",
    "oj": "Ons Jabeur",

    "vondrousova": "Markéta Vondroušová",
    "markéta vondroušová": "Markéta Vondroušová",
    "marketa vondrousova": "Markéta Vondroušová", # Common spelling without diacritics
    "mv": "Markéta Vondroušová",

    "sakkari": "Maria Sakkari",
    "maria sakkari": "Maria Sakkari",
    "ms": "Maria Sakkari",

    "muchova": "Karolína Muchová",
    "karolína muchová": "Karolína Muchová",
    "karolina muchova": "Karolína Muchová", # Common spelling without diacritics
    "km": "Karolína Muchová",

    "zheng": "Qinwen Zheng",
    "qinwen zheng": "Qinwen Zheng",
    "qz": "Qinwen Zheng",

    "osaka": "Naomi Osaka",
    "naomi osaka": "Naomi Osaka",
    "no": "Naomi Osaka",

    # === Add more players and aliases as needed ===
}