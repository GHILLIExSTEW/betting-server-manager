# League Data/data/league/league_dictionaries/ufc.py
"""
UFC Fighter names and aliases based on recent rankings and nicknames.
Key: lowercase alias/nickname/full name
Value: Standardized Full Name
"""

UFC_FIGHTERS = {
    # === Men's Champions (as of ~April 2025) ===
    "jon jones": "Jon Jones",
    "jones": "Jon Jones",
    "bones": "Jon Jones",
    "tom aspinall": "Tom Aspinall",
    "aspinall": "Tom Aspinall", # HW Interim
    "magomed ankalaev": "Magomed Ankalaev",
    "ankalaev": "Magomed Ankalaev", # LHW
    "dricus du plessis": "Dricus du Plessis",
    "du plessis": "Dricus du Plessis",
    "stillknocks": "Dricus du Plessis", # MW
    "belal muhammad": "Belal Muhammad",
    "muhammad": "Belal Muhammad",
    "remember the name": "Belal Muhammad", # WW
    "islam makhachev": "Islam Makhachev",
    "makhachev": "Islam Makhachev", # LW
    "ilia topuria": "Ilia Topuria",
    "topuria": "Ilia Topuria",
    "el matador": "Ilia Topuria", # FW
    "merab dvalishvili": "Merab Dvalishvili",
    "dvalishvili": "Merab Dvalishvili",
    "the machine": "Merab Dvalishvili", # BW
    "alexandre pantoja": "Alexandre Pantoja",
    "pantoja": "Alexandre Pantoja",
    "the cannibal": "Alexandre Pantoja", # FLW

    # === Women's Champions (as of ~April 2025) ===
    "julianna peña": "Julianna Peña",
    "julianna pena": "Julianna Peña", # Alt spelling
    "peña": "Julianna Peña",
    "pena": "Julianna Peña", # Alt spelling
    "the venezuelan vixen": "Julianna Peña", # BW
    "valentina shevchenko": "Valentina Shevchenko",
    "shevchenko": "Valentina Shevchenko",
    "bullet": "Valentina Shevchenko", # FLW
    "zhang weili": "Zhang Weili",
    "weili zhang": "Zhang Weili", # Common inversion
    "weili": "Zhang Weili",
    "magnum": "Zhang Weili", # SW

    # === Top Ranked / Notable Fighters & Nicknames ===
    "alex pereira": "Alex Pereira",
    "pereira": "Alex Pereira",
    "poatan": "Alex Pereira",
    "alexander volkanovski": "Alexander Volkanovski",
    "volkanovski": "Alexander Volkanovski",
    "volk": "Alexander Volkanovski",
    "the great": "Alexander Volkanovski",
    "max holloway": "Max Holloway",
    "holloway": "Max Holloway",
    "blessed": "Max Holloway",
    "sean o'malley": "Sean O'Malley",
    "sean o malley": "Sean O'Malley", # Alt spelling
    "o'malley": "Sean O'Malley",
    "omalley": "Sean O'Malley", # Alt spelling
    "suga": "Sean O'Malley",
    "charles oliveira": "Charles Oliveira",
    "oliveira": "Charles Oliveira",
    "do bronx": "Charles Oliveira",
    "arman tsarukyan": "Arman Tsarukyan",
    "tsarukyan": "Arman Tsarukyan",
    "khamzat chimaev": "Khamzat Chimaev",
    "chimaev": "Khamzat Chimaev",
    "borz": "Khamzat Chimaev",
    "israel adesanya": "Israel Adesanya",
    "adesanya": "Israel Adesanya",
    "the last stylebender": "Israel Adesanya",
    "stylebender": "Israel Adesanya",
    "robert whittaker": "Robert Whittaker",
    "whittaker": "Robert Whittaker",
    "the reaper": "Robert Whittaker",
    "bobby knuckles": "Robert Whittaker",
    "sean strickland": "Sean Strickland",
    "strickland": "Sean Strickland",
    "tarzan": "Sean Strickland",
    "shavkat rakhmonov": "Shavkat Rakhmonov",
    "rakhmonov": "Shavkat Rakhmonov",
    "nomad": "Shavkat Rakhmonov",
    "leon edwards": "Leon Edwards",
    "edwards": "Leon Edwards",
    "rocky": "Leon Edwards",
    "kamaru usman": "Kamaru Usman",
    "usman": "Kamaru Usman",
    "the nigerian nightmare": "Kamaru Usman",
    "jiri prochazka": "Jiří Procházka",
    "jiří procházka": "Jiří Procházka", # With diacritic
    "prochazka": "Jiří Procházka",
    "denisa": "Jiří Procházka",
    "jamahal hill": "Jamahal Hill",
    "hill": "Jamahal Hill",
    "sweet dreams": "Jamahal Hill",
    "ciryl gane": "Ciryl Gane",
    "gane": "Ciryl Gane",
    "bon gamin": "Ciryl Gane",
    "sergei pavlovich": "Sergei Pavlovich",
    "pavlovich": "Sergei Pavlovich",
    "curtis blaydes": "Curtis Blaydes",
    "blaydes": "Curtis Blaydes",
    "razor": "Curtis Blaydes",
    "justin gaethje": "Justin Gaethje",
    "gaethje": "Justin Gaethje",
    "the highlight": "Justin Gaethje",
    "dustin poirier": "Dustin Poirier",
    "poirier": "Dustin Poirier",
    "the diamond": "Dustin Poirier",
    "paddy pimblett": "Paddy Pimblett",
    "pimblett": "Paddy Pimblett",
    "the baddy": "Paddy Pimblett",
    "petr yan": "Petr Yan",
    "yan": "Petr Yan",
    "no mercy": "Petr Yan",
    "cory sandhagen": "Cory Sandhagen",
    "sandhagen": "Cory Sandhagen",
    "sandman": "Cory Sandhagen",
    "brandon moreno": "Brandon Moreno",
    "moreno": "Brandon Moreno",
    "the assassin baby": "Brandon Moreno",
    "brandon royval": "Brandon Royval",
    "royval": "Brandon Royval",
    "raw dawg": "Brandon Royval",
    "alexa grasso": "Alexa Grasso",
    "grasso": "Alexa Grasso",
    "tatiana suarez": "Tatiana Suarez",
    "suarez": "Tatiana Suarez",
    "rose namajunas": "Rose Namajunas",
    "namajunas": "Rose Namajunas",
    "thug rose": "Rose Namajunas",
    "jessica andrade": "Jéssica Andrade",
    "jéssica andrade": "Jéssica Andrade", # With diacritic
    "andrade": "Jéssica Andrade",
    "bate estaca": "Jéssica Andrade",

    # === Legends / Other Common Names ===
    "conor mcgregor": "Conor McGregor",
    "mcgregor": "Conor McGregor",
    "notorious": "Conor McGregor",
    "chan sung jung": "Chan Sung Jung",
    "korean zombie": "Chan Sung Jung",
    "anderson silva": "Anderson Silva",
    "silva": "Anderson Silva",
    "the spider": "Anderson Silva",
    "carlos condit": "Carlos Condit",
    "condit": "Carlos Condit",
    "the natural born killer": "Carlos Condit",
    "quinton jackson": "Quinton Jackson",
    "rampage": "Quinton Jackson",
    "rampage jackson": "Quinton Jackson",
    "wanderlei silva": "Wanderlei Silva",
    "the axe murderer": "Wanderlei Silva",
    "chuck liddell": "Chuck Liddell",
    "liddell": "Chuck Liddell",
    "the iceman": "Chuck Liddell",
    "georges st-pierre": "Georges St-Pierre",
    "georges st pierre": "Georges St-Pierre", # Alt spelling
    "gsp": "Georges St-Pierre",
    "rush": "Georges St-Pierre",
    "khabib nurmagomedov": "Khabib Nurmagomedov",
    "khabib": "Khabib Nurmagomedov",
    "nurmagomedov": "Khabib Nurmagomedov",
    "the eagle": "Khabib Nurmagomedov",

    # Add more as needed...
}

# Optional: If you need specific abbreviations separate from aliases
# UFC_ABBREVIATIONS = {
#    "Jon Jones": "JJ",
#    "Islam Makhachev": "IM",
# }