"""
Comprehensive Channel Database for EPG Matching
Contains network feeds, cable channels, Canadian broadcasters, and known mappings
"""

# ============================================================================
# US NETWORK FEEDS (National/Regional Feeds - No Local Affiliates)
# These map directly to network feed XMLIDs
# ============================================================================
US_NETWORK_FEEDS = {
    # ABC Network Feeds
    "ABC EAST": "ABC.East.us",
    "ABC WEST": "ABC.West.us",
    "ABC EAST HD": "ABC.East.us",
    "ABC WEST HD": "ABC.West.us",
    
    # NBC Network Feeds
    "NBC EAST": "NBC.East.us",
    "NBC WEST": "NBC.West.us",
    "NBC EAST HD": "NBC.East.us",
    "NBC WEST HD": "NBC.West.us",
    
    # CBS Network Feeds
    "CBS EAST": "CBS.East.us",
    "CBS WEST": "CBS.West.us",
    "CBS EAST HD": "CBS.East.us",
    "CBS WEST HD": "CBS.West.us",
    
    # FOX Network Feeds
    "FOX EAST": "FOX.East.us",
    "FOX WEST": "FOX.West.us",
    "FOX EAST HD": "FOX.East.us",
    "FOX WEST HD": "FOX.West.us",
    
    # CW Network Feeds
    "CW EAST": "CW.us",
    "CW WEST": "CW.us",
    "CW EAST HD": "CW.us",
    "CW WEST HD": "CW.us",
    
    # PBS Network
    "PBS": "PBS.us",
    "PBS HD": "PBS.us",
    "PBS KIDS": "PBSKids.us",
}

# ============================================================================
# US CABLE/SATELLITE CHANNELS (National Channels)
# ============================================================================
US_CABLE_CHANNELS = {
    # News Networks
    "CNN": "CNN.us",
    "CNN HD": "CNN.us",
    "CNN INTERNATIONAL": "CNNI.us",
    "FOX NEWS": "FoxNews.us",
    "FOX NEWS HD": "FoxNews.us",
    "FOX BUSINESS": "FoxBusiness.us",
    "MSNBC": "MSNBC.us",
    "MSNBC HD": "MSNBC.us",
    "CNBC": "CNBC.us",
    "CNBC HD": "CNBC.us",
    "BLOOMBERG": "Bloomberg.us",
    "BBC WORLD NEWS": "BBCWorldNews.us",
    "BBC AMERICA": "BBCAmerica.us",
    "C-SPAN": "CSPAN.us",
    "C-SPAN 2": "CSPAN2.us",
    "C-SPAN 3": "CSPAN3.us",
    "NEWSMAX": "Newsmax.us",
    "NEWSNATION": "NewsNation.us",
    "HLN": "HLN.us",
    "WEATHER CHANNEL": "WeatherChannel.us",
    "CBS NEWS": "CBSNews.us",
    "ABC NEWS LIVE": "ABCNewsLive.us",
    
    # Sports Networks
    "ESPN": "ESPN.us",
    "ESPN HD": "ESPN.us",
    "ESPN2": "ESPN2.us",
    "ESPN2 HD": "ESPN2.us",
    "ESPNU": "ESPNU.us",
    "ESPN NEWS": "ESPNNews.us",
    "ESPN DEPORTES": "ESPNDeportes.us",
    "ESPN+": "ESPNPlus.us",
    "FS1": "FS1.us",
    "FS1 HD": "FS1.us",
    "FS2": "FS2.us",
    "FOX SPORTS 1": "FS1.us",
    "FOX SPORTS 2": "FS2.us",
    "NFL NETWORK": "NFLNetwork.us",
    "NFL REDZONE": "NFLRedZone.us",
    "MLB NETWORK": "MLBNetwork.us",
    "NBA TV": "NBATV.us",
    "NHL NETWORK": "NHLNetwork.us",
    "GOLF CHANNEL": "GolfChannel.us",
    "TENNIS CHANNEL": "TennisChannel.us",
    "CBS SPORTS NETWORK": "CBSSN.us",
    "NBC SPORTS": "NBCSports.us",
    "BIG TEN NETWORK": "BigTenNetwork.us",
    "BTN": "BigTenNetwork.us",
    "SEC NETWORK": "SECNetwork.us",
    "ACC NETWORK": "ACCNetwork.us",
    "PAC-12 NETWORK": "Pac12Network.us",
    "BEIN SPORTS": "beINSports.us",
    "BEIN SPORTS 2": "beINSports2.us",
    "OLYMPIC CHANNEL": "OlympicChannel.us",
    "TUDN": "TUDN.us",
    "FOX DEPORTES": "FoxDeportes.us",
    "MAV TV": "MavTV.us",
    "MAVTV": "MavTV.us",
    "OUTDOOR CHANNEL": "OutdoorChannel.us",
    "SPORTSMAN CHANNEL": "SportsmanChannel.us",
    
    # Entertainment Networks
    "TNT": "TNT.us",
    "TNT HD": "TNT.us",
    "TBS": "TBS.us",
    "TBS HD": "TBS.us",
    "USA NETWORK": "USANetwork.us",
    "USA": "USANetwork.us",
    "FX": "FX.us",
    "FX HD": "FX.us",
    "FXX": "FXX.us",
    "AMC": "AMC.us",
    "AMC HD": "AMC.us",
    "A&E": "AE.us",
    "AE": "AE.us",
    "BRAVO": "Bravo.us",
    "E!": "E.us",
    "SYFY": "Syfy.us",
    "COMEDY CENTRAL": "ComedyCentral.us",
    "MTV": "MTV.us",
    "VH1": "VH1.us",
    "BET": "BET.us",
    "CMT": "CMT.us",
    "PARAMOUNT NETWORK": "ParamountNetwork.us",
    "TV LAND": "TVLand.us",
    "TVLAND": "TVLand.us",
    "WE TV": "WeTV.us",
    "LIFETIME": "Lifetime.us",
    "LMN": "LMN.us",
    "HALLMARK CHANNEL": "HallmarkChannel.us",
    "HALLMARK MOVIES": "HallmarkMovies.us",
    "ION": "ION.us",
    "ION TELEVISION": "ION.us",
    "OWN": "OWN.us",
    "OXYGEN": "Oxygen.us",
    "REELZ": "Reelz.us",
    "POP": "Pop.us",
    "FREEFORM": "Freeform.us",
    "TLC": "TLC.us",
    "HGTV": "HGTV.us",
    "FOOD NETWORK": "FoodNetwork.us",
    "DIY NETWORK": "DIYNetwork.us",
    "COOKING CHANNEL": "CookingChannel.us",
    "TRAVEL CHANNEL": "TravelChannel.us",
    "DISCOVERY": "Discovery.us",
    "DISCOVERY CHANNEL": "Discovery.us",
    "ANIMAL PLANET": "AnimalPlanet.us",
    "SCIENCE CHANNEL": "ScienceChannel.us",
    "INVESTIGATION DISCOVERY": "ID.us",
    "ID": "ID.us",
    "HISTORY": "History.us",
    "HISTORY CHANNEL": "History.us",
    "H2": "H2.us",
    "HISTORY 2": "H2.us",
    "MILITARY HISTORY": "MilitaryHistory.us",
    "A&E CRIME": "AECrime.us",
    "AMERICAN HEROES CHANNEL": "AHC.us",
    "AHC": "AHC.us",
    "DESTINATION AMERICA": "DestinationAmerica.us",
    "NAT GEO": "NatGeo.us",
    "NATIONAL GEOGRAPHIC": "NatGeo.us",
    "NAT GEO WILD": "NatGeoWild.us",
    "SMITHSONIAN": "Smithsonian.us",
    "SMITHSONIAN CHANNEL": "Smithsonian.us",
    "NASA TV": "NASATV.us",
    "NASA": "NASATV.us",
    "NASA HD": "NASATV.us",
    "FYI": "FYI.us",
    
    # Premium Movie Channels
    "HBO": "HBO.us",
    "HBO HD": "HBO.us",
    "HBO 2": "HBO2.us",
    "HBO SIGNATURE": "HBOSignature.us",
    "HBO FAMILY": "HBOFamily.us",
    "HBO COMEDY": "HBOComedy.us",
    "HBO ZONE": "HBOZone.us",
    "HBO LATINO": "HBOLatino.us",
    "CINEMAX": "Cinemax.us",
    "MAX": "MAX.us",
    "SHOWTIME": "Showtime.us",
    "SHOWTIME HD": "Showtime.us",
    "SHOWTIME 2": "Showtime2.us",
    "SHO 2": "Showtime2.us",
    "SHOWTIME EXTREME": "ShowtimeExtreme.us",
    "SHOWTIME BEYOND": "ShowtimeBeyond.us",
    "SHOWTIME NEXT": "ShowtimeNext.us",
    "SHOWTIME WOMEN": "ShowtimeWomen.us",
    "SHOWTIME FAMILY": "ShowtimeFamily.us",
    "STARZ": "Starz.us",
    "STARZ HD": "Starz.us",
    "STARZ EDGE": "StarzEdge.us",
    "STARZ ENCORE": "StarzEncore.us",
    "STARZ CINEMA": "StarzCinema.us",
    "STARZ KIDS": "StarzKids.us",
    "EPIX": "Epix.us",
    "MGM+": "MGMPlus.us",
    "TMC": "TMC.us",
    "THE MOVIE CHANNEL": "TMC.us",
    "FLIX": "Flix.us",
    "SUNDANCE TV": "SundanceTV.us",
    "IFC": "IFC.us",
    "TCM": "TCM.us",
    "TURNER CLASSIC MOVIES": "TCM.us",
    
    # Kids Channels
    "NICKELODEON": "Nickelodeon.us",
    "NICK": "Nickelodeon.us",
    "NICK JR": "NickJr.us",
    "NICKTOONS": "Nicktoons.us",
    "TEENICK": "TeenNick.us",
    "DISNEY CHANNEL": "DisneyChannel.us",
    "DISNEY JR": "DisneyJr.us",
    "DISNEY XD": "DisneyXD.us",
    "CARTOON NETWORK": "CartoonNetwork.us",
    "BOOMERANG": "Boomerang.us",
    "PBS KIDS": "PBSKids.us",
    "BABY TV": "BabyTV.us",
    "UNIVERSAL KIDS": "UniversalKids.us",
    "DISCOVERY FAMILY": "DiscoveryFamily.us",
    
    # Spanish Language
    "UNIVISION": "Univision.us",
    "TELEMUNDO": "Telemundo.us",
    "GALAVISION": "Galavision.us",
    "UNIMAS": "UniMas.us",
    "ESTRELLA TV": "EstrellaTV.us",
    "AZTECA": "Azteca.us",
    "BANDAMAX": "Bandamax.us",
    "CINE LATINO": "CineLatino.us",
    "DISCOVERY EN ESPANOL": "DiscoveryEspanol.us",
    "ESPN DEPORTES": "ESPNDeportes.us",
    "FOX DEPORTES": "FoxDeportes.us",
    "HISTORY EN ESPANOL": "HistoryEspanol.us",
    "MTV TR3S": "MTVTR3S.us",
    "TELEMUNDO DEPORTES": "TelemundoDeportes.us",
    
    # Music Channels
    "MTV LIVE": "MTVLive.us",
    "MTV CLASSIC": "MTVClassic.us",
    "MTV2": "MTV2.us",
    "BET JAMS": "BETJams.us",
    "BET SOUL": "BETSoul.us",
    "CMT MUSIC": "CMTMusic.us",
    
    # Shopping/Lifestyle
    "QVC": "QVC.us",
    "QVC 2": "QVC2.us",
    "HSN": "HSN.us",
    "SHOP NBC": "ShopNBC.us",
    
    # WGN America
    "WGN": "WGN.us",
    "WGN AMERICA": "WGNAmerica.us",
    "WGN HD": "WGN.us",
    
    # Peachtree TV
    "PEACHTREE TV": "PeachtreeTV.us",
    "PEACH TREE": "PeachtreeTV.us",
    "PEACH TREE HD": "PeachtreeTV.us",
}

# ============================================================================
# CANADIAN CHANNELS
# ============================================================================
CANADIAN_CHANNELS = {
    # CBC Channels
    "CBC EAST": "CBC.East.ca",
    "CBC WEST": "CBC.West.ca",
    "CBC EAST HD": "CBC.East.ca",
    "CBC WEST HD": "CBC.West.ca",
    "CBC TORONTO": "CBLT.ca",
    "CBC VANCOUVER": "CBUT.ca",
    "CBC OTTAWA": "CBOT.ca",
    "CBC WINNIPEG": "CBWT.ca",
    "CBC EDMONTON": "CBXT.ca",
    "CBC CALGARY": "CBRT.ca",
    "CBC MONTREAL": "CBMT.ca",
    "CBC HALIFAX": "CBHT.ca",
    "CBC CHARLOTTETOWN": "CBCT.ca",
    "CBC FREDERICTON": "CBAT.ca",
    "CBC FREDERICTON HD": "CBAT.ca",
    "CBC NEWS NETWORK": "CBCNewsNetwork.ca",
    "CBC NEWS": "CBCNewsNetwork.ca",
    
    # CTV Channels
    "CTV": "CTV.ca",
    "CTV EAST": "CTV.East.ca",
    "CTV WEST": "CTV.West.ca",
    "CTV TORONTO": "CFTO.ca",
    "CTV OTTAWA": "CJOH.ca",
    "CTV OTTAWA HD": "CJOH.ca",
    "CTV VANCOUVER": "CIVT.ca",
    "CTV MONTREAL": "CFCF.ca",
    "CTV WINNIPEG": "CKY.ca",
    "CTV CALGARY": "CFCN.ca",
    "CTV EDMONTON": "CFRN.ca",
    "CTV 2": "CTV2.ca",
    "CTV 2 VICTORIA": "CIVI.ca",
    "CTV 2 VICTORIA HD": "CIVI.ca",
    "CTV NEWS": "CTVNews.ca",
    "CTV NEWS CHANNEL": "CTVNewsChannel.ca",
    
    # Global Channels
    "GLOBAL": "Global.ca",
    "GLOBAL EAST": "Global.East.ca",
    "GLOBAL WEST": "Global.West.ca",
    "GLOBAL EAST HD": "Global.East.ca",
    "GLOBAL TORONTO": "CIII.ca",
    "GLOBAL VANCOUVER": "CHAN.ca",
    "GLOBAL VANCOUVER HD": "CHAN.ca",
    "GLOBAL VANCOUVER/BC": "CHAN.ca",
    "GLOBAL VANCOUVER/BC HD": "CHAN.ca",
    "GLOBAL WINNIPEG": "CKND.ca",
    "GLOBAL WINNIPEG HD": "CKND.ca",
    "GLOBAL HALIFAX": "CIHF.ca",
    "GLOBAL CALGARY": "CICT.ca",
    "GLOBAL EDMONTON": "CITV.ca",
    "GLOBAL KINGSTON": "CKWS.ca",
    "GLOBAL KINGSTON HD": "CKWS.ca",
    "GLOBAL NEWS": "GlobalNews.ca",
    "GLOBAL NEWS HALIFAX": "GlobalNews.Halifax.ca",
    "GLOBAL NEWS WINNIPEG": "GlobalNews.Winnipeg.ca",
    
    # Citytv
    "CITYTV": "Citytv.ca",
    "CITY": "Citytv.ca",
    "CITY TV": "Citytv.ca",
    "CITYTV TORONTO": "CITY.ca",
    "CITYTV VANCOUVER": "CKVU.ca",
    "CITYTV CALGARY": "CKAL.ca",
    "CITYTV EDMONTON": "CKEM.ca",
    "CITYTV MONTREAL": "CJNT.ca",
    "CITYTV WINNIPEG": "CHMI.ca",
    
    # TVA (French)
    "TVA": "TVA.ca",
    "TVA MONTREAL": "CFTM.ca",
    "TVA MONTREAL HD": "CFTM.ca",
    "TVA QUEBEC CITY": "CFCM.ca",
    "TVA QUEBEC CITY HD": "CFCM.ca",
    "TVA HULL": "CFTVO.ca",
    "TVA HULL HD": "CFTVO.ca",
    "TVA SHERBROOKE": "CHLT.ca",
    "TVA SAGUENAY": "CJPM.ca",
    "TVA RIMOUSKI": "CJBR.ca",
    "TVA CARLETON SUR MER": "CHAU.ca",
    "TVA RIVIERE DU LOUP": "CKRT.ca",
    "TVA RIVIERE DU LOUP HD": "CKRT.ca",
    "TVA SPORTS": "TVASports.ca",
    
    # Radio-Canada (French CBC)
    "ICI RADIO CANADA": "RadioCanada.ca",
    "ICI RADIO-CANADA": "RadioCanada.ca",
    "RDI": "RDI.ca",
    "ICI RDI": "RDI.ca",
    
    # Specialty Channels
    "TSN": "TSN.ca",
    "TSN 1": "TSN1.ca",
    "TSN 2": "TSN2.ca",
    "TSN 3": "TSN3.ca",
    "TSN 4": "TSN4.ca",
    "TSN 5": "TSN5.ca",
    "SPORTSNET": "Sportsnet.ca",
    "SPORTSNET ONE": "SportsnetOne.ca",
    "SPORTSNET EAST": "SportsnetEast.ca",
    "SPORTSNET WEST": "SportsnetWest.ca",
    "SPORTSNET ONTARIO": "SportsnetOntario.ca",
    "SPORTSNET PACIFIC": "SportsnetPacific.ca",
    "SPORTSNET 360": "Sportsnet360.ca",
    "RDS": "RDS.ca",
    "RDS HD": "RDS.ca",
    "RDS 2": "RDS2.ca",
    "RDS 2 HD": "RDS2.ca",
    "RDS INFO": "RDSInfo.ca",
    "RDS INFO HD": "RDSInfo.ca",
    
    # News Channels
    "CP24": "CP24.ca",
    "CP24 HD": "CP24.ca",
    "BNN": "BNN.ca",
    "BNN HD": "BNN.ca",
    "BNN BLOOMBERG": "BNNBloomberg.ca",
    "LCN": "LCN.ca",
    "LCN HD": "LCN.ca",
    "CPAC": "CPAC.ca",
    "CPAC HD": "CPAC.ca",
    "CPAC FRENCH": "CPACFrench.ca",
    "CPAC HD FRENCH": "CPACFrench.ca",
    
    # Lifestyle/Entertainment
    "MUCH": "Much.ca",
    "MUCHMUSIC": "Much.ca",
    "MTV CANADA": "MTVCanada.ca",
    "SPACE": "Space.ca",
    "SHOWCASE": "Showcase.ca",
    "SLICE": "Slice.ca",
    "W NETWORK": "WNetwork.ca",
    "OLN": "OLN.ca",
    "OLN HD": "OLN.ca",
    "DISCOVERY CANADA": "DiscoveryCanada.ca",
    "DISCOVERY VELOCITY": "DiscoveryVelocity.ca",
    "DISCOVERY VELOCITY HD": "DiscoveryVelocity.ca",
    "HISTORY CANADA": "HistoryCanada.ca",
    "HGTV CANADA": "HGTVCanada.ca",
    "FOOD NETWORK CANADA": "FoodNetworkCanada.ca",
    "TLC CANADA": "TLCCanada.ca",
    "CRIME + INVESTIGATION": "CrimeInvestigation.ca",
    "BOOK TV": "BookTV.ca",
    "BBC CANADA": "BBCCanada.ca",
    "MAKEFUL": "Makeful.ca",
    "MAKEFUL HD": "Makeful.ca",
    "FYI CANADA": "FYICanada.ca",
    "FYI HD": "FYICanada.ca",
    
    # Kids
    "TELETOON": "Teletoon.ca",
    "TELETOON HD": "Teletoon.ca",
    "TELETOON FRENCH": "TeletoonFrench.ca",
    "TELETOON FRENCH HD": "TeletoonFrench.ca",
    "FAMILY CHANNEL": "Family.ca",
    "FAMILY": "Family.ca",
    "FAMILY JR": "FamilyJr.ca",
    "FAMILY JUNIOR": "FamilyJr.ca",
    "FAMILY JUNIOR HD": "FamilyJr.ca",
    "TREEHOUSE": "Treehouse.ca",
    "YTV": "YTV.ca",
    "DISNEY CANADA": "DisneyCanada.ca",
    "WILD BRAIN TV": "WildBrainTV.ca",
    "WILD BRAIN": "WildBrainTV.ca",
    
    # Movies
    "CRAVE": "Crave.ca",
    "CRAVE HD": "Crave.ca",
    "CRAVE 1": "Crave1.ca",
    "CRAVE 2": "Crave2.ca",
    "CRAVE 3": "Crave3.ca",
    "CRAVE 4": "Crave4.ca",
    "CRAVE 4 HD": "Crave4.ca",
    "SUPER CHANNEL": "SuperChannel.ca",
    "SUPER ECRAN": "SuperEcran.ca",
    "MOVIE TIME": "MovieTime.ca",
    
    # French Specialty
    "TELE QUEBEC": "TeleQuebec.ca",
    "TELE QUEBEC HD": "TeleQuebec.ca",
    "CANAL SAVOIR": "CanalSavoir.ca",
    "CANAL VIE": "CanalVie.ca",
    "CASA": "Casa.ca",
    "EVASION": "Evasion.ca",
    "SERIES+": "SeriesPlus.ca",
    "TV5": "TV5.ca",
    "TV5 MONDE": "TV5Monde.ca",
    "VRAK": "Vrak.ca",
    "Z": "Z.ca",
    "METEO MEDIA": "MeteoMedia.ca",
    "METEO MEDIA HD": "MeteoMedia.ca",
    "PLANETE+ CANADA": "PlanetePlus.ca",
    
    # Regional
    "CHCH": "CHCH.ca",
    "CHCH HD": "CHCH.ca",
    "YES TV": "YesTV.ca",
    "YES TV HD": "YesTV.ca",
    "YES BURLINGTON": "YesTVBurlington.ca",
    "YES BURLINGTON HD": "YesTVBurlington.ca",
    "OMNI 1": "OMNI1.ca",
    "OMNI 2": "OMNI2.ca",
    "OMNI 2 HD": "OMNI2.ca",
    "JOYTV": "JoyTV.ca",
    "JOYTV (BC)": "JoyTV.ca",
    "JOYTV (BC) HD": "JoyTV.ca",
    "MIRACLE": "MiracleChannel.ca",
    "MIRACLE HD": "MiracleChannel.ca",
    "SALT LIGHT": "SaltLight.ca",
    "SALT LIGHT HD": "SaltLight.ca",
    "TLN": "TLN.ca",
    "TELEMAG": "Telemag.ca",
    
    # Rogers TV
    "ROGERS TV": "RogersTV.ca",
    "ROGERS TV LONDON": "RogersTVLondon.ca",
    "ROGERS TV TORONTO": "RogersTVToronto.ca",
    
    # Fashion/Music
    "FASHION TELEVISION": "FashionTV.ca",
    "FASHION TELEVISION CHANNEL": "FashionTV.ca",
    "FTV CANADA": "FashionTV.ca",
    "STINGRAY": "Stingray.ca",
    
    # Travel
    "TRAVEL AND ESCAPE": "TravelEscape.ca",
    "TRAVEL AND ESCAPE HD": "TravelEscape.ca",
    
    # One Get Fit
    "ONE GET FIT": "OneGetFit.ca",
    "ONE GET FIT HD": "OneGetFit.ca",
    
    # Fireplace channels
    "FEU DE FOYER": "FeuDefoyer.ca",
    "FEU DE FOYER HD": "FeuDefoyer.ca",
}

# ============================================================================
# UK CHANNELS
# ============================================================================
UK_CHANNELS = {
    # BBC
    "BBC ONE": "BBC1.uk",
    "BBC ONE HD": "BBC1.uk",
    "BBC ONE SCOTLAND": "BBC1Scotland.uk",
    "BBC ONE SCOTLAND HD": "BBC1Scotland.uk",
    "BBC ONE SCOTLAND HEVC": "BBC1Scotland.uk",
    "BBC ONE WALES": "BBC1Wales.uk",
    "BBC ONE WALES HD": "BBC1Wales.uk",
    "BBC ONE WALES HEVC": "BBC1Wales.uk",
    "BBC ONE EAST MIDLANDS": "BBC1EastMidlands.uk",
    "BBC ONE CHANNEL ISLAND": "BBC1ChannelIslands.uk",
    "BBC TWO": "BBC2.uk",
    "BBC TWO HD": "BBC2.uk",
    "BBC THREE": "BBC3.uk",
    "BBC FOUR": "BBC4.uk",
    "BBC 4 / CBEEBIES": "BBC4.uk",
    "BBC 4 / CBEEBIES HEVC": "BBC4.uk",
    "BBC NEWS": "BBCNews.uk",
    "BBC NEWS HD": "BBCNews.uk",
    "BBC NEWS HEVC": "BBCNews.uk",
    "BBC NEWS HEVC HD": "BBCNews.uk",
    "BBC NEWS HEVC FHD": "BBCNews.uk",
    "BBC PARLIAMENT": "BBCParliament.uk",
    "BBC SCOTLAND": "BBCScotland.uk",
    "BBC ALBA": "BBCAlba.uk",
    "CBBC": "CBBC.uk",
    "CBEEBIES": "CBeebies.uk",
    
    # ITV
    "ITV": "ITV.uk",
    "ITV HD": "ITV.uk",
    "ITV 1": "ITV.uk",
    "ITV 2": "ITV2.uk",
    "ITV 3": "ITV3.uk",
    "ITV 4": "ITV4.uk",
    "ITVBE": "ITVBe.uk",
    "ITVBe": "ITVBe.uk",
    "CITV": "CITV.uk",
    
    # Channel 4
    "CHANNEL 4": "Channel4.uk",
    "CHANNEL 4 HD": "Channel4.uk",
    "4 HD": "Channel4.uk",
    "E4": "E4.uk",
    "MORE4": "More4.uk",
    "FILM4": "Film4.uk",
    "4SEVEN": "4Seven.uk",
    
    # Channel 5
    "CHANNEL 5": "Channel5.uk",
    "CHANNEL 5 HD": "Channel5.uk",
    "5 USA": "5USA.uk",
    "5 STAR": "5Star.uk",
    "5 ACTION": "5Action.uk",
    "5 SELECT": "5Select.uk",
    
    # Sky
    "SKY ONE": "SkyOne.uk",
    "SKY TWO": "SkyTwo.uk",
    "SKY NEWS": "SkyNews.uk",
    "SKY NEWS HD": "SkyNews.uk",
    "SKY SPORTS": "SkySports.uk",
    "SKY ATLANTIC": "SkyAtlantic.uk",
    "SKY ARTS": "SkyArts.uk",
    "SKY CINEMA": "SkyCinema.uk",
    "SKY DOCUMENTARIES": "SkyDocumentaries.uk",
    "SKY HISTORY": "SkyHistory.uk",
    "SKY NATURE": "SkyNature.uk",
    "SKY CRIME": "SkyCrime.uk",
    "SKY COMEDY": "SkyComedy.uk",
    "SKY MAX": "SkyMax.uk",
    "SKY WITNESS": "SkyWitness.uk",
    
    # UKTV
    "DAVE": "Dave.uk",
    "GOLD": "Gold.uk",
    "W": "W.uk",
    "ALIBI": "Alibi.uk",
    "ALIBI HD": "Alibi.uk",
    "ALIBI HEVC HD": "Alibi.uk",
    "YESTERDAY": "Yesterday.uk",
    "DRAMA": "Drama.uk",
    "EDEN": "Eden.uk",
    
    # Discovery UK
    "DISCOVERY UK": "DiscoveryUK.uk",
    "QUEST": "Quest.uk",
    "QUEST RED": "QuestRed.uk",
    "REALLY": "Really.uk",
    "FOOD NETWORK UK": "FoodNetworkUK.uk",
    "HGTV UK": "HGTVUK.uk",
    "DMAX": "DMAX.uk",
    
    # Others
    "90'S - DIRECT": "90sTV.uk",
}

# ============================================================================
# STINGRAY MUSIC CHANNELS (Canadian Music Service)
# ============================================================================
STINGRAY_CHANNELS = {
    "STINGRAY ADULT ALTERNATIVE": "StingrayAdultAlternative.ca",
    "STINGRAY CLASSIC MASTERS": "StingrayClassicMasters.ca",
    "STINGRAY COUNTRY CLASSICS": "StingrayCountryClassics.ca",
    "STINGRAY EASY LISTENTING": "StingrayEasyListening.ca",
    "STINGRAY EASY LISTENING": "StingrayEasyListening.ca",
    "STINGRAY FRANCO COUNTRY": "StingrayFrancoCountry.ca",
    "STINGRAY FRANCO RETRO": "StingrayFrancoRetro.ca",
    "STINGRAY GREATEST HITS": "StingrayGreatestHits.ca",
    "STINGRAY HOT COUNTRY": "StingrayHotCountry.ca",
    "STINGRAY JUKEBOX OLDIES": "StingrayJukeboxOldies.ca",
    "STINGRAY LE PALMARÈS": "StingrayLePalmares.ca",
    "STINGRAY LE PALMARES": "StingrayLePalmares.ca",
    "STINGRAY NOSTALGIE": "StingrayNostalgie.ca",
    "STINGRAY ROCK": "StingrayRock.ca",
    "STINGRAY ROMANCE LATINO": "StingrayRomanceLatino.ca",
    "STINGRAY SMOOTH JAZZ": "StingraySmoothJazz.ca",
    "STINGRAY SOUVENIRS": "StingraySouvenirs.ca",
    "STINGRAY SPECIAL": "StingraySpecial.ca",
    "STINGRAY THE BLUES": "StingrayTheBlues.ca",
    "STINGRAY THE CHILL LOUNGE": "StingrayChillLounge.ca",
    "STINGRAY TODAY'S LATIN POP": "StingrayLatinPop.ca",
    "STINGRAY TODAYS LATIN POP": "StingrayLatinPop.ca",
}

# ============================================================================
# ASIAN CHANNELS (Common in CA/US IPTV packages)
# ============================================================================
ASIAN_CHANNELS = {
    "ATN IBC TAMIL": "ATNIBCTamil.ca",
    "ATN MTV INDIA": "ATNMTVIndia.ca",
    "FUJIAN TV": "FujianTV.cn",
    "JIANGSU": "JiangsuTV.cn",
    "TET": "TET.vn",
    "SAB CANADA": "SABCanada.ca",
    "TELEBIMBI": "Telebimbi.it",
    "TELENINOS": "Teleninos.es",
    "CARIBBEAN RADIO": "CaribbeanRadio.ca",
    "WIN TV CARIBBEAN": "WinTVCaribbean.ca",
    "WOWTV": "WOWTV.ca",
    "RECORD INTERNATIONAL": "RecordInternational.br",
}

# ============================================================================
# SUPER SPORTS CHANNELS (Rogers Super Sports Pack - Canada)
# ============================================================================
SUPER_SPORTS_CHANNELS = {}
for ch_num in range(267, 500):
    SUPER_SPORTS_CHANNELS[f"SUPER SPORTS CH {ch_num}"] = f"SuperSports{ch_num}.ca"
# Handle combined channel numbers
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 431/476"] = "SuperSports431.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 432/472"] = "SuperSports432.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 454/477"] = "SuperSports454.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 455/478"] = "SuperSports455.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 456/479"] = "SuperSports456.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 457/480"] = "SuperSports457.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 458/481"] = "SuperSports458.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 459/482"] = "SuperSports459.ca"
SUPER_SPORTS_CHANNELS["SUPER SPORTS CH 460/483"] = "SuperSports460.ca"

# ============================================================================
# TORONTO LIVE CHANNELS
# ============================================================================
TORONTO_CHANNELS = {
    "TORONTO LIVE 1": "TorontoLive1.ca",
    "TORONTO LIVE 2": "TorontoLive2.ca",
    "TORONTO LIVE 3": "TorontoLive3.ca",
    "TORONTO LIVE 4": "TorontoLive4.ca",
}

# ============================================================================
# APPLE TV+ CHANNELS (UK Package)
# ============================================================================
APPLE_TV_CHANNELS = {}
for i in range(1, 20):
    APPLE_TV_CHANNELS[f"APPLE TV+ SERIES {i}"] = f"AppleTVSeries{i}.uk"
    APPLE_TV_CHANNELS[f"APPLE TV+ SERIES {i} ᴴᴰ"] = f"AppleTVSeries{i}.uk"
APPLE_TV_CHANNELS["APPLE TV+ SERIES info"] = "AppleTVInfo.uk"
APPLE_TV_CHANNELS["APPLE TV+ SERIES info ᴴᴰ"] = "AppleTVInfo.uk"

# ============================================================================
# WSBK Channel (Boston UPN/CW affiliate commonly carried in Canada)
# ============================================================================
US_BORDER_STATIONS = {
    "WSBK": "WSBK.us",
    "WSBK HD": "WSBK.us",
}


def get_all_known_channels():
    """Return combined dictionary of all known channel mappings"""
    all_channels = {}
    all_channels.update(US_NETWORK_FEEDS)
    all_channels.update(US_CABLE_CHANNELS)
    all_channels.update(CANADIAN_CHANNELS)
    all_channels.update(UK_CHANNELS)
    all_channels.update(STINGRAY_CHANNELS)
    all_channels.update(ASIAN_CHANNELS)
    all_channels.update(SUPER_SPORTS_CHANNELS)
    all_channels.update(TORONTO_CHANNELS)
    all_channels.update(APPLE_TV_CHANNELS)
    all_channels.update(US_BORDER_STATIONS)
    return all_channels


def normalize_channel_name(name):
    """
    Normalize channel name for matching:
    - Remove region prefix (CA|, US|, UK|, etc.)
    - Strip whitespace
    - Remove HD/SD suffixes for matching
    - Handle special characters
    """
    import re
    
    # Remove region prefix
    name = re.sub(r'^[A-Z]+\|\s*', '', name)
    
    # Remove special unicode characters (like superscript HD markers)
    name = name.replace('ᴴᴰ', 'HD').replace('ᴿᴬᴰ', '').replace('á´´á´°', 'HD')
    
    # Strip and normalize whitespace
    name = ' '.join(name.split())
    
    return name.strip()


def lookup_channel(raw_name):
    """
    Look up a channel by its raw IPTV name.
    Returns (xmlid, confidence) or (None, 0)
    """
    normalized = normalize_channel_name(raw_name)
    all_channels = get_all_known_channels()
    
    # Exact match (case-insensitive)
    for known_name, xmlid in all_channels.items():
        if normalized.upper() == known_name.upper():
            return xmlid, 100
    
    # Try without HD suffix
    normalized_no_hd = normalized.replace(' HD', '').replace(' SD', '').strip()
    for known_name, xmlid in all_channels.items():
        known_no_hd = known_name.replace(' HD', '').replace(' SD', '').strip()
        if normalized_no_hd.upper() == known_no_hd.upper():
            return xmlid, 95
    
    return None, 0
