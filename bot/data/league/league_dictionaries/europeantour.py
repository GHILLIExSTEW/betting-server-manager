# League Data/data/league/league_dictionaries/europeantour.py
"""
DP World Tour (European Tour) Golfer names and aliases.
Key: lowercase full name (or common alias)
Value: Standardized Full Name
Based on Race to Dubai rankings around April 2025.
"""

EUROPEANTOUR_GOLFERS = {
    # Top Ranked Players (Race to Dubai - Example based on search results)
    "laurie canter": "Laurie Canter",
    "canter": "Laurie Canter",
    "tyrrell hatton": "Tyrrell Hatton",
    "hatton": "Tyrrell Hatton",
    "john parry": "John Parry",
    "parry": "John Parry",
    "shaun norris": "Shaun Norris",
    "norris": "Shaun Norris",
    "daniel hillier": "Daniel Hillier",
    "hillier": "Daniel Hillier",
    "jacques kruyswijk": "Jacques Kruyswijk",
    "kruyswijk": "Jacques Kruyswijk",
    "keita nakajima": "Keita Nakajima",
    "nakajima": "Keita Nakajima",
    "haotong li": "Haotong Li",
    "li haotong": "Haotong Li", # Common inversion
    "dylan naidoo": "Dylan Naidoo",
    "naidoo": "Dylan Naidoo",
    "johannes veerman": "Johannes Veerman",
    "veerman": "Johannes Veerman",
    "richard mansell": "Richard Mansell",
    "mansell": "Richard Mansell",
    "elvis smylie": "Elvis Smylie",
    "smylie": "Elvis Smylie",
    "alejandro del rey": "Alejandro Del Rey",
    "del rey": "Alejandro Del Rey",
    "calum hill": "Calum Hill",
    "hill": "Calum Hill", # Ambiguous, use full name preferably
    "eugenio chacarra": "Eugenio Chacarra",
    "chacarra": "Eugenio Chacarra",
    "marcus armitage": "Marcus Armitage",
    "armitage": "Marcus Armitage",
    "adrien saddier": "Adrien Saddier",
    "saddier": "Adrien Saddier",
    "rasmus neergaard-petersen": "Rasmus Neergaard-Petersen",
    "neergaard-petersen": "Rasmus Neergaard-Petersen",
    "ryggs johnston": "Ryggs Johnston",
    "johnston": "Ryggs Johnston", # Ambiguous
    "matthew jordan": "Matthew Jordan",
    "jordan": "Matthew Jordan", # Ambiguous
    "jayden schaper": "Jayden Schaper",
    "schaper": "Jayden Schaper",
    "tom mckibbin": "Tom McKibbin",
    "mckibbin": "Tom McKibbin",
    "brandon robinson-thompson": "Brandon Robinson-Thompson",
    "robinson-thompson": "Brandon Robinson-Thompson",
    "ivan cantero": "Ivan Cantero",
    "cantero": "Ivan Cantero",
    "joost luiten": "Joost Luiten",
    "luiten": "Joost Luiten",
    "romain langasque": "Romain Langasque",
    "langasque": "Romain Langasque",
    "daniel brown": "Daniel Brown",
    "brown": "Daniel Brown", # Ambiguous
    "martin couvra": "Martin Couvra",
    "couvra": "Martin Couvra",
    "pablo larrazabal": "Pablo Larrazábal",
    "pablo larrazábal": "Pablo Larrazábal", # With diacritic
    "larrazabal": "Pablo Larrazábal",
    "angel ayora": "Angel Ayora",
    "ayora": "Angel Ayora",
    "dylan frittelli": "Dylan Frittelli",
    "frittelli": "Dylan Frittelli",
    "niklas norgaard": "Niklas Norgaard",
    "norgaard": "Niklas Norgaard",
    "ryan van velzen": "Ryan Van Velzen",
    "van velzen": "Ryan Van Velzen",
    "david micheluzzi": "David Micheluzzi",
    "micheluzzi": "David Micheluzzi",
    "wenyi ding": "Wenyi Ding",
    "ding wenyi": "Wenyi Ding", # Common inversion
    "ricardo gouveia": "Ricardo Gouveia",
    "gouveia": "Ricardo Gouveia",
    "jens dantorp": "Jens Dantorp",
    "dantorp": "Jens Dantorp",
    "deon germishuys": "Deon Germishuys",
    "germishuys": "Deon Germishuys",
    "andrea pavan": "Andrea Pavan",
    "pavan": "Andrea Pavan",
    "marcus kinhult": "Marcus Kinhult",
    "kinhult": "Marcus Kinhult",
    "francesco laporta": "Francesco Laporta",
    "laporta": "Francesco Laporta",
    "julien guerrier": "Julien Guerrier",
    "guerrier": "Julien Guerrier",
    "jason scrivener": "Jason Scrivener",
    "scrivener": "Jason Scrivener",
    "marco penge": "Marco Penge",
    "penge": "Marco Penge",
    "ugo coussaud": "Ugo Coussaud",
    "coussaud": "Ugo Coussaud",
    "brandon stone": "Brandon Stone",
    "stone": "Brandon Stone", # Ambiguous
    "sam bairstow": "Sam Bairstow",
    "bairstow": "Sam Bairstow",
    "freddy schott": "Freddy Schott",
    "schott": "Freddy Schott",
    "jordan smith": "Jordan Smith",
    "smith": "Jordan Smith", # Ambiguous
    "thorbjorn olesen": "Thorbjørn Olesen",
    "thorbjørn olesen": "Thorbjørn Olesen", # With diacritic
    "olesen": "Thorbjørn Olesen",
    "richie ramsay": "Richie Ramsay",
    "ramsay": "Richie Ramsay",
    "andy sullivan": "Andy Sullivan",
    "sullivan": "Andy Sullivan",
    "jordan gumberg": "Jordan Gumberg",
    "gumberg": "Jordan Gumberg",
    "kiradech aphibarnrat": "Kiradech Aphibarnrat",
    "aphibarnrat": "Kiradech Aphibarnrat",
    "connor syme": "Connor Syme",
    "syme": "Connor Syme",

    # Other notable DP World / European Tour players
    "rory mcilroy": "Rory McIlroy", # Often plays DPWT events
    "mcilroy": "Rory McIlroy",
    "justin rose": "Justin Rose",
    "rose": "Justin Rose",
    "robert macintyre": "Robert MacIntyre",
    "macintyre": "Robert MacIntyre",
    "bob macintyre": "Robert MacIntyre", # Nickname
    "rasmus hojgaard": "Rasmus Højgaard",
    "rasmus højgaard": "Rasmus Højgaard", # With diacritic
    "nicolai hojgaard": "Nicolai Højgaard",
    "nicolai højgaard": "Nicolai Højgaard", # With diacritic
    "hojgaard": "Rasmus Højgaard", # Ambiguous - default to Rasmus or require full name?
    "thomas detry": "Thomas Detry",
    "detry": "Thomas Detry",
    "thriston lawrence": "Thriston Lawrence",
    "lawrence": "Thriston Lawrence",
    "aaron rai": "Aaron Rai",
    "rai": "Aaron Rai",
    "shane lowry": "Shane Lowry", # Often plays DPWT events
    "lowry": "Shane Lowry",
    "tommy fleetwood": "Tommy Fleetwood", # Often plays DPWT events
    "fleetwood": "Tommy Fleetwood",
    "matthew fitzpatrick": "Matthew Fitzpatrick", # Often plays DPWT events
    "fitzpatrick": "Matthew Fitzpatrick",
    "sepp straka": "Sepp Straka", # Often plays DPWT events
    "straka": "Sepp Straka",
    "viktor hovland": "Viktor Hovland", # Often plays DPWT events
    "hovland": "Viktor Hovland",

    # LIV players who might play DPWT events
    "jon rahm": "Jon Rahm",
    "rahm": "Jon Rahm",
    "adrian meronk": "Adrian Meronk",
    "meronk": "Adrian Meronk",
    "dean burmester": "Dean Burmester",
    "burmester": "Dean Burmester",
    "joaquin niemann": "Joaquin Niemann",
    "niemann": "Joaquin Niemann",
    "thomas pieters": "Thomas Pieters",
    "pieters": "Thomas Pieters",
    "patrick reed": "Patrick Reed",
    "reed": "Patrick Reed",
    "lucas herbert": "Lucas Herbert",
    "herbert": "Lucas Herbert",
    "sergio garcia": "Sergio Garcia", # If returns to DPWT
    "garcia": "Sergio Garcia",

    # Add more players and aliases as needed...
}

# Optional: Abbreviations if commonly used for specific players
# EUROPEANTOUR_ABBREVIATIONS = {
#    "Rory McIlroy": "RM",
#    "Tyrrell Hatton": "TH",
# }