"""NASCAR Cup Series team names and abbreviations for the 2025 season."""

NASCAR_ABBREVIATIONS = {
    # Full-Time Chartered Teams (18 organizations, 36 charters)
    "hms": "Hendrick Motorsports",       # 4 cars: #5 Larson, #9 Elliott, #24 Byron, #48 Bowman
    "jgr": "Joe Gibbs Racing",           # 4 cars: #11 Hamlin, #19 Briscoe, #20 Bell, #54 Gibbs
    "penske": "Team Penske",             # 3 cars: #2 Cindric, #12 Blaney, #22 Logano
    "rfk": "RFK Racing",                 # 3 cars: #6 Keselowski, #17 Buescher, #60 Preece
    "23xi": "23XI Racing",               # 3 cars: #23 Wallace, #35 Herbst, #45 Reddick
    "track": "Trackhouse Racing",        # 3 cars: #1 Chastain, #88 van Gisbergen, #99 Suarez
    "rcr": "Richard Childress Racing",   # 2 cars: #3 Dillon, #8 Busch
    "frm": "Front Row Motorsports",      # 3 cars: #34 Gilliland, #36 Gragson, #38 Smith
    "spire": "Spire Motorsports",        # 3 cars: #7 Haley, #71 McDowell, #77 Hocevar
    "lmc": "Legacy Motor Club",          # 2 cars: #42 Nemechek, #43 Jones
    "haas": "Haas Factory Team",         # 1 car: #41 Custer
    "hyak": "Hyak Motorsports",          # 1 car: #47 Stenhouse Jr.
    "kaul": "Kaulig Racing",             # 2 cars: #10 Dillon, #16 Allmendinger
    "wood": "Wood Brothers Racing",      # 1 car: #21 Berry
    "rwr": "Rick Ware Racing",           # 1 car: #51 Ware
    "jr": "JR Motorsports",              # 1 car: #56 Truex Jr. (part-time/full-time TBD)

    # Notable Part-Time/Open Teams
    "g66": "Garage 66",                  # Part-time, no full-time charter, various drivers
    "tricon": "TRICON Garage",           # Part-time, #01 or #15, various drivers
    "beard": "Beard Motorsports",        # Part-time, #62, typically Daytona/Talladega
    "live": "Live Fast Motorsports",     # Part-time, #78, occasional races
}

TEAM_FULL_NAMES = {
    # Aliases and common nicknames
    "hendrick": "Hendrick Motorsports",
    "gibbs": "Joe Gibbs Racing",
    "penske": "Team Penske",
    "roush": "RFK Racing",               # Historical nod to Roush Racing
    "rfk racing": "RFK Racing",
    "23xi": "23XI Racing",
    "trackhouse": "Trackhouse Racing",
    "childress": "Richard Childress Racing",
    "rcr": "Richard Childress Racing",
    "front row": "Front Row Motorsports",
    "spire": "Spire Motorsports",
    "legacy": "Legacy Motor Club",
    "haas": "Haas Factory Team",
    "hyak": "Hyak Motorsports",
    "kaulig": "Kaulig Racing",
    "wood brothers": "Wood Brothers Racing",
    "ware": "Rick Ware Racing",
    "jrm": "JR Motorsports",
    "garage 66": "Garage 66",
    "tricon": "TRICON Garage",
    "beard": "Beard Motorsports",
    "live fast": "Live Fast Motorsports",
    "hms": "Hendrick Motorsports",
    "jgr": "Joe Gibbs Racing",
    "team penske": "Team Penske",
}

"""NASCAR Cup Series driver names and car numbers for the 2025 season."""

DRIVER_NAMES = {
    # Full-Time Chartered Teams (18 organizations, 36 charters)
    "Hendrick Motorsports": ["5 Kyle Larson", "9 Chase Elliott", "24 William Byron", "48 Alex Bowman"],
    "Joe Gibbs Racing": ["11 Denny Hamlin", "19 Chase Briscoe", "20 Christopher Bell", "54 Ty Gibbs"],
    "Team Penske": ["2 Austin Cindric", "12 Ryan Blaney", "22 Joey Logano"],
    "RFK Racing": ["6 Brad Keselowski", "17 Chris Buescher", "60 Ryan Preece"],
    "23XI Racing": ["23 Bubba Wallace", "35 Riley Herbst", "45 Tyler Reddick"],
    "Trackhouse Racing": ["1 Ross Chastain", "88 Shane van Gisbergen", "99 Daniel Suarez"],
    "Richard Childress Racing": ["3 Austin Dillon", "8 Kyle Busch"],
    "Front Row Motorsports": ["34 Michael Gilliland", "36 Noah Gragson", "38 Zane Smith"],
    "Spire Motorsports": ["7 Justin Haley", "71 Michael McDowell", "77 Carson Hocevar"],
    "Legacy Motor Club": ["42 John Hunter Nemechek", "43 Erik Jones"],
    "Haas Factory Team": ["41 Cole Custer"],
    "Hyak Motorsports": ["47 Ricky Stenhouse Jr."],
    "Kaulig Racing": ["10 Ty Dillon", "16 AJ Allmendinger"],
    "Wood Brothers Racing": ["21 Josh Berry"],
    "Rick Ware Racing": ["51 Cody Ware"],
    "JR Motorsports": ["56 Martin Truex Jr."],  # Part-time/full-time TBD

    # Notable Part-Time/Open Teams (drivers vary by race)
    "Garage 66": [""],  # Part-time, no fixed driver
    "TRICON Garage": [""],  # Part-time, often #01 or #15
    "Beard Motorsports": ["62 Anthony Alfredo"],  # Typically Daytona/Talladega
    "Live Fast Motorsports": ["78 BJ McLeod"],  # Part-time, occasional races
}