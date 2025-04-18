# utils/league_dictionaries/nhl.py

NHL_ABBREVIATIONS = {
    "ana": "Anaheim Ducks",
    "ari": "Arizona Coyotes",
    "bos": "Boston Bruins",
    "buf": "Buffalo Sabres",
    "cgy": "Calgary Flames",
    "car": "Carolina Hurricanes",
    "chi": "Chicago Blackhawks",
    "col": "Colorado Avalanche",
    "cbj": "Columbus Blue Jackets",
    "dal": "Dallas Stars",
    "det": "Detroit Red Wings",
    "edm": "Edmonton Oilers",
    "fla": "Florida Panthers",
    "lak": "Los Angeles Kings",
    "min": "Minnesota Wild",
    "mtl": "Montreal Canadiens",
    "nsh": "Nashville Predators",
    "njd": "New Jersey Devils",
    "nyi": "New York Islanders",
    "nyr": "New York Rangers",
    "ott": "Ottawa Senators",
    "phi": "Philadelphia Flyers",
    "pit": "Pittsburgh Penguins",
    "sj": "San Jose Sharks",
    "stl": "St. Louis Blues",
    "tbl": "Tampa Bay Lightning",
    "tor": "Toronto Maple Leafs",
    "uhc": "Utah Hockey Club",
    "van": "Vancouver Canucks",
    "vgk": "Vegas Golden Knights",
    "wsh": "Washington Capitals",
    "wpg": "Winnipeg Jets",
    # Common callouts
    "kraken": "Seattle Kraken"
}

TEAM_FULL_NAMES = {
    # Anaheim Ducks
    "ana": "Anaheim Ducks",
    "anaheim": "Anaheim Ducks",
    "ducks": "Anaheim Ducks",
    "anaheim ducks": "Anaheim Ducks",

    # Arizona Coyotes
    "ari": "Arizona Coyotes",
    "arizona": "Arizona Coyotes",
    "coyotes": "Arizona Coyotes",
    "arizona coyotes": "Arizona Coyotes",

    # Boston Bruins
    "bos": "Boston Bruins",
    "boston": "Boston Bruins",
    "bruins": "Boston Bruins",
    "boston bruins": "Boston Bruins",

    # Buffalo Sabres
    "buf": "Buffalo Sabres",
    "buffalo": "Buffalo Sabres",
    "sabres": "Buffalo Sabres",
    "buffalo sabres": "Buffalo Sabres",

    # Calgary Flames
    "cgy": "Calgary Flames",
    "calgary": "Calgary Flames",
    "flames": "Calgary Flames",
    "calgary flames": "Calgary Flames",

    # Carolina Hurricanes
    "car": "Carolina Hurricanes",
    "carolina": "Carolina Hurricanes",
    "hurricanes": "Carolina Hurricanes",
    "carolina hurricanes": "Carolina Hurricanes",

    # Chicago Blackhawks
    "chi": "Chicago Blackhawks",
    "chicago": "Chicago Blackhawks",
    "blackhawks": "Chicago Blackhawks",
    "chicago blackhawks": "Chicago Blackhawks",

    # Colorado Avalanche
    "col": "Colorado Avalanche",
    "colorado": "Colorado Avalanche",
    "avalanche": "Colorado Avalanche",
    "colorado avalanche": "Colorado Avalanche",

    # Columbus Blue Jackets
    "cbj": "Columbus Blue Jackets",
    "columbus": "Columbus Blue Jackets",
    "blue jackets": "Columbus Blue Jackets",
    "columbus blue jackets": "Columbus Blue Jackets",

    # Dallas Stars
    "dal": "Dallas Stars",
    "dallas": "Dallas Stars",
    "stars": "Dallas Stars",
    "dallas stars": "Dallas Stars",

    # Detroit Red Wings
    "det": "Detroit Red Wings",
    "detroit": "Detroit Red Wings",
    "red wings": "Detroit Red Wings",
    "detroit red wings": "Detroit Red Wings",

    # Edmonton Oilers
    "edm": "Edmonton Oilers",
    "edmonton": "Edmonton Oilers",
    "oilers": "Edmonton Oilers",
    "edmonton oilers": "Edmonton Oilers",

    # Florida Panthers
    "fla": "Florida Panthers",
    "florida": "Florida Panthers",
    "panthers": "Florida Panthers",
    "florida panthers": "Florida Panthers",

    # Los Angeles Kings
    "lak": "Los Angeles Kings",
    "los angeles kings": "Los Angeles Kings",
    "kings": "Los Angeles Kings",
    "la kings": "Los Angeles Kings",

    # Minnesota Wild
    "min": "Minnesota Wild",
    "minnesota": "Minnesota Wild",
    "wild": "Minnesota Wild",
    "minnesota wild": "Minnesota Wild",

    # Montreal Canadiens
    "mtl": "Montreal Canadiens",
    "montreal": "Montreal Canadiens",
    "canadiens": "Montreal Canadiens",
    "montreal canadiens": "Montreal Canadiens",

    # Nashville Predators
    "nsh": "Nashville Predators",
    "nashville": "Nashville Predators",
    "predators": "Nashville Predators",
    "nashville predators": "Nashville Predators",

    # New Jersey Devils
    "njd": "New Jersey Devils",
    "new jersey": "New Jersey Devils",
    "devils": "New Jersey Devils",
    "new jersey devils": "New Jersey Devils",

    # New York Islanders
    "nyi": "New York Islanders",
    "new york islanders": "New York Islanders",
    "islanders": "New York Islanders",

    # New York Rangers
    "nyr": "New York Rangers",
    "new york rangers": "New York Rangers",
    "rangers": "New York Rangers",

    # Ottawa Senators
    "ott": "Ottawa Senators",
    "ottawa": "Ottawa Senators",
    "senators": "Ottawa Senators",
    "ottawa senators": "Ottawa Senators",

    # Philadelphia Flyers
    "phi": "Philadelphia Flyers",
    "philadelphia": "Philadelphia Flyers",
    "flyers": "Philadelphia Flyers",
    "philadelphia flyers": "Philadelphia Flyers",

    # Pittsburgh Penguins
    "pit": "Pittsburgh Penguins",
    "pittsburgh": "Pittsburgh Penguins",
    "penguins": "Pittsburgh Penguins",
    "pittsburgh penguins": "Pittsburgh Penguins",

    # San Jose Sharks
    "sj": "San Jose Sharks",
    "san jose": "San Jose Sharks",
    "sharks": "San Jose Sharks",
    "san jose sharks": "San Jose Sharks",

    # St. Louis Blues
    "stl": "St. Louis Blues",
    "st. louis": "St. Louis Blues",
    "blues": "St. Louis Blues",
    "st. louis blues": "St. Louis Blues",

    # Tampa Bay Lightning
    "tbl": "Tampa Bay Lightning",
    "tampa bay": "Tampa Bay Lightning",
    "lightning": "Tampa Bay Lightning",
    "tampa bay lightning": "Tampa Bay Lightning",

    # Toronto Maple Leafs
    "tor": "Toronto Maple Leafs",
    "toronto": "Toronto Maple Leafs",
    "maple leafs": "Toronto Maple Leafs",
    "maple leaves": "Toronto Maple Leafs",
    "toronto maple leafs": "Toronto Maple Leafs",
    "toronto maple leaves": "Toronto Maple Leafs",
    
    # Utah Hockey Club
    "uhc": "Utah Hockey Club",
    "utah": "Utah Hockey Club",
    "hockey club": "Utah Hockey Club",
    "utsh": "Utah Hockey Club",

    # Vancouver Canucks
    "van": "Vancouver Canucks",
    "vancouver": "Vancouver Canucks",
    "canucks": "Vancouver Canucks",
    "vancouver canucks": "Vancouver Canucks",
    "utsh hockey club": "Vancouver Canucks",  # Handling common miscall

    # Vegas Golden Knights
    "vgk": "Vegas Golden Knights",
    "vegas": "Vegas Golden Knights",
    "golden knights": "Vegas Golden Knights",
    "vegas golden knights": "Vegas Golden Knights",

    # Washington Capitals
    "wsh": "Washington Capitals",
    "washington": "Washington Capitals",
    "capitals": "Washington Capitals",
    "washington capitals": "Washington Capitals",

    # Winnipeg Jets
    "wpg": "Winnipeg Jets",
    "winnipeg": "Winnipeg Jets",
    "jets": "Winnipeg Jets",
    "winnipeg jets": "Winnipeg Jets",

    # Extra common callouts
    "kraken": "Seattle Kraken",
    "seattle kraken": "Seattle Kraken"
}
