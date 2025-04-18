# League Data/data/league/league_dictionaries/atp.py
"""
ATP (Men's Tennis) Player names.
Key: lowercase full name (or common alias)
Value: Standardized Full Name
Based on rankings around April 2025. Add aliases as needed.
"""

ATP_PLAYERS = {
    # Top Ranked Players (Example based on search results)
    "jannik sinner": "Jannik Sinner",
    "sinner": "Jannik Sinner",
    "carlos alcaraz": "Carlos Alcaraz",
    "alcaraz": "Carlos Alcaraz",
    "alexander zverev": "Alexander Zverev",
    "zverev": "Alexander Zverev",
    "sascha zverev": "Alexander Zverev", # Common nickname
    "taylor fritz": "Taylor Fritz",
    "fritz": "Taylor Fritz",
    "novak djokovic": "Novak Djokovic",
    "djokovic": "Novak Djokovic",
    "nole": "Novak Djokovic", # Common nickname
    "jack draper": "Jack Draper",
    "draper": "Jack Draper",
    "alex de minaur": "Alex de Minaur",
    "de minaur": "Alex de Minaur",
    "demon": "Alex de Minaur", # Common nickname
    "andrey rublev": "Andrey Rublev",
    "rublev": "Andrey Rublev",
    "daniil medvedev": "Daniil Medvedev",
    "medvedev": "Daniil Medvedev",
    "casper ruud": "Casper Ruud",
    "ruud": "Casper Ruud",
    "lorenzo musetti": "Lorenzo Musetti",
    "musetti": "Lorenzo Musetti",
    "tommy paul": "Tommy Paul",
    "paul": "Tommy Paul",
    "holger rune": "Holger Rune",
    "rune": "Holger Rune",
    "arthur fils": "Arthur Fils",
    "fils": "Arthur Fils",
    "ben shelton": "Ben Shelton",
    "shelton": "Ben Shelton",
    "stefanos tsitsipas": "Stefanos Tsitsipas",
    "tsitsipas": "Stefanos Tsitsipas",
    "grigor dimitrov": "Grigor Dimitrov",
    "dimitrov": "Grigor Dimitrov",
    "frances tiafoe": "Frances Tiafoe",
    "tiafoe": "Frances Tiafoe",
    "big foe": "Frances Tiafoe", # Common nickname
    "felix auger aliassime": "Félix Auger-Aliassime",
    "félix auger-aliassime": "Félix Auger-Aliassime", # With diacritic
    "auger aliassime": "Félix Auger-Aliassime",
    "faa": "Félix Auger-Aliassime", # Common abbreviation
    "tomas machac": "Tomáš Macháč",
    "tomáš macháč": "Tomáš Macháč", # With diacritics
    "machac": "Tomáš Macháč",
    "ugo humbert": "Ugo Humbert",
    "humbert": "Ugo Humbert",
    "francisco cerundolo": "Francisco Cerúndolo",
    "francisco cerúndolo": "Francisco Cerúndolo", # With diacritic
    "cerundolo": "Francisco Cerúndolo",
    "jakub mensik": "Jakub Menšík",
    "jakub menšík": "Jakub Menšík", # With diacritic
    "mensik": "Jakub Menšík",
    "sebastian korda": "Sebastian Korda",
    "korda": "Sebastian Korda",
    "alexei popyrin": "Alexei Popyrin",
    "popyrin": "Alexei Popyrin",
    "jiri lehecka": "Jiří Lehečka",
    "jiří lehečka": "Jiří Lehečka", # With diacritics
    "lehecka": "Jiří Lehečka",
    "karen khachanov": "Karen Khachanov",
    "khachanov": "Karen Khachanov",
    "hubert hurkacz": "Hubert Hurkacz",
    "hurkacz": "Hubert Hurkacz",
    "denis shapovalov": "Denis Shapovalov",
    "shapovalov": "Denis Shapovalov",
    "shapo": "Denis Shapovalov", # Common nickname
    "alejandro davidovich fokina": "Alejandro Davidovich Fokina",
    "davidovich fokina": "Alejandro Davidovich Fokina",
    "foki": "Alejandro Davidovich Fokina", # Common nickname

    # Add other relevant players and aliases...
    # Consider adding legends if needed
    "rafael nadal": "Rafael Nadal",
    "nadal": "Rafael Nadal",
    "rafa": "Rafael Nadal",
    "roger federer": "Roger Federer",
    "federer": "Roger Federer",

}

# ATP likely doesn't need TEAM_FULL_NAMES or specific ABBREVIATIONS
# unless you treat tournaments or countries like teams.