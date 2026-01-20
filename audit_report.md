# Match Audit Report
**Total Reviewed:** 780

| Input Name | Current Match | Reason for Flag |
|---|---|---|
| (No suspicious matches found) | - | - |
| ##### CW MONTANA ##### \| US\| CW/MY NETWORK | KTVQ.us | NETWORK MISMATCH: KTVQ is the primary CBS affiliate for Billings, MT; the CW is only a subchannel. |
| ##### FOX NEW MEXICO ##### \| US\| FOX NETWORK | KRQE.us | NETWORK MISMATCH: KRQE is the primary CBS affiliate for Albuquerque. While it carries FOX on a subchannel (13.2), the XMLID "KRQE.us" typically points to primary CBS programming schedules. |
| ##### FOX SOUTH DAKOTA ##### \| US\| FOX NETWORK | KTTW.us | NETWORK MISMATCH: KTTW lost its FOX affiliation in 2020 (now a TCT affiliate); FOX programming in that market moved to KDLT-DT2. |
| ##### FOX WEST VIRGINIA ##### \| US\| FOX NETWORK | WVAH.us | NETWORK MISMATCH: WVAH lost its FOX affiliation in 2021 (now Catchy Comedy); FOX programming in that market moved to WCHS-DT2. |
| (FLSP 278) \| flohoops: 2025 Hamline vs George Fox University _ Men`s (Hamline vs George Fox) (2025-12-29 21:00:10) | US\| FLO NETWORK | FloHoops.us | MISSED LOCALIZATION: Specific event stream (FLSP 278) mapped to a generic network XMLID; will not provide event-specific EPG data. |
| (FLSP 579) \| flohoops: 2026 College of Biblical Studies vs Concordia (TX) _ Women`s (CBS vs Concordia (TX)) (2026-01-01 18:00:05) | US\| FLO NETWORK | FloHoops.us | MISSED LOCALIZATION: Specific event stream (FLSP 579) mapped to a generic network XMLID; will not provide event-specific EPG data. |
| PRIME\| ABC CHARLESTON NEWS (WCIV.2) ᴴᴰ \| US\| PRIME | WCIV.us | NETWORK MISMATCH: WCIV (36.1) is an NBC affiliate. The input specifies WCIV.2, which is the ABC subchannel. Mapping to the primary "WCIV.us" ID will provide incorrect NBC program listings. |
| (No suspicious matches found) | | |
| PRIME\| CBS NEWS ᴿᴬᴰ \| CA\| PRIME ᴿᴬᴰ ⁶⁰ᶠᵖˢ | CBSNews.us | **Network/Region Mismatch**: Input is flagged for Canada (CA) region, but mapped to a US national XMLID (.us). |
| PRIME\| CW GOLD ᴿᴬᴰ \| US\| PRIME | CW.us | **Missed Localization/Generic**: "CW Gold" is a specific digital/FAST sub-brand with distinct programming, mapped to the generic main CW network ID. |
| (No suspicious matches found) | | |
| (No suspicious matches found) | N/A | All mappings provided are 100% accurate. Fox affiliates are correctly mapped to their specific FCC callsigns (e.g., KSAZ, KTTV, KDFW), the NBC affiliate is correctly mapped to its callsign (WPTV), and the CBS News and PBS sub-channels are correctly mapped to their specific streaming/digital identities. |
| SPORTS\| MY SUPERSPORTS 1 HD \| ASIA \| SPORTS | SuperSport1.my | MISSED LOCALIZATION: Mapped to generic SuperSport name. In Malaysia (MY), this network is "Astro SuperSport". |
| SPORTS\| MY SUPERSPORTS 2 HD \| ASIA \| SPORTS | SuperSport2.my | MISSED LOCALIZATION: Mapped to generic SuperSport name. In Malaysia (MY), this network is "Astro SuperSport". |
| SPORTS\| MY SUPERSPORTS 3 HD \| ASIA \| SPORTS | SuperSport3.my | MISSED LOCALIZATION: Mapped to generic SuperSport name. In Malaysia (MY), this network is "Astro SuperSport". |
| SPORTS\| MY SUPERSPORTS 4 HD \| ASIA \| SPORTS | SuperSport4.my | MISSED LOCALIZATION: Mapped to generic SuperSport name. In Malaysia (MY), this network is "Astro SuperSport". |
| US\| ABC 18 MIAMI FL (WSVN-D2) \| US\| ABC NETWORK | WSVN.us | **NETWORK MISMATCH / LOCALIZATION**: WSVN is the FOX affiliate for Miami (Channel 7). The ABC affiliate in Miami is WPLG. Additionally, mapping a subchannel (D2) to the main station XMLID without the subchannel suffix is imprecise. |
| US\| ABC 20 SPRINGFIELD IL (WICS) \| US\| ABC NETWORK | WICS.us | NETWORK MISMATCH: WICS (Channel 20) is an NBC affiliate; the ABC affiliate for this market is WAND. |
| US\| ABC 33 BIRMINGHAM AL (WABM) \| US\| ABC NETWORK | WABM.us | NETWORK MISMATCH: WABM is the MyNetworkTV affiliate for Birmingham. The ABC affiliate is WBMA (often branded as ABC 33/40). |
| **No suspicious matches found** | **N/A** | All 30 entries passed validation for network alignment, localization accuracy, and format. |
| (No suspicious matches found) | | |
| US\| CBS 13 GULFPORT MS (WLOX) \| US\| CBS NETWORK | WLOX.us | NETWORK MISMATCH: WLOX's primary channel (13.1) is an ABC affiliate. CBS is carried on their subchannel (13.2). Mapping to the generic "WLOX.us" XMLID typically results in ABC EPG data instead of CBS. |
| US\| CBS 3 IDAHO FALLS (KIFI) \| US\| CBS NETWORK | KIFI.us | **NETWORK MISMATCH**: KIFI is primarily an ABC affiliate (Channel 8). While they carry CBS on a subchannel, the XMLID `KIFI.us` typically points to ABC programming. The CBS affiliate for Idaho Falls on Channel 3 is KIDK. |
| US\| CBS 3 WILMINGTON NC (WWAY) \| US\| CBS NETWORK | WWAY.us | NETWORK MISMATCH: WWAY is primarily an ABC affiliate; the CBS network is carried on its subchannel (3.2), usually requiring a distinct XMLID (e.g., WWAY2.us). |
| US\| CBS 40 BOWLING GREEN KY (WNKY) \| US\| CBS NETWORK | WNKY.us | NETWORK MISMATCH: WNKY is primarily an NBC affiliate; the CBS network is carried on its subchannel (40.2), usually requiring a distinct XMLID (e.g., WNKY2.us). |
| US\| CBS 4 RIO GRANDE VALLEY TX (KGBT) \| US\| CBS NETWORK | KGBT.us | NETWORK MISMATCH: KGBT-TV is no longer a CBS affiliate (it is now Independent/MyNetworkTV); the CBS affiliation in this market moved to KVEO-DT2. |
| US\| CBS 9 LOS ANGELES CA (KCAL) \| US\| CBS NETWORK | KCAL.us | NETWORK MISMATCH: KCAL is an Independent station, not a CBS affiliate. The CBS affiliate for Los Angeles is KCBS (Channel 2). |
| US\| CW 25 (WEEK) PEORIA \| US\| CW/MY NETWORK | WEEK.us | **NETWORK MISMATCH:** WEEK is primarily an NBC affiliate. Mapping the CW feed to the main station ID will likely result in NBC programming instead of the CW subchannel. |
| US\| CW 27 LEXINGTON (WKYT) \| US\| CW/MY NETWORK | WKYT.us | **NETWORK MISMATCH:** WKYT is primarily a CBS affiliate. Mapping the CW feed to the main station ID will likely result in CBS programming instead of the CW subchannel. |
| US\| CW 5 PALM SPRINGS CA (KESQ) \| US\| CW/MY NETWORK | KESQ.us | **NETWORK MISMATCH:** KESQ is primarily an ABC affiliate. Mapping the CW feed to the main station ID will likely result in ABC programming instead of the CW subchannel. |
| US\| CW 6 SAN DIEGO CA (KFMB) \| US\| CW/MY NETWORK | KFMB.us | NETWORK MISMATCH: KFMB is a primary CBS affiliate; CW is carried on a digital subchannel (8.2). XMLID likely serves CBS data. |
| US\| CW 8 MISSOULA MT (KPAX) \| US\| CW/MY NETWORK | KPAX.us | NETWORK MISMATCH: KPAX is a primary CBS affiliate; CW is carried on a digital subchannel (8.2). XMLID likely serves CBS data. |
| US\| FOX 10 TERRE HAUTE IN (WTHI) \| US\| FOX NETWORK | WTHI.us | NETWORK MISMATCH: WTHI is a primary CBS affiliate; FOX is carried on a digital subchannel (10.2). |
| US\| FOX 12 SHERMAN TX (KXII) \| US\| FOX NETWORK | KXII.us | NETWORK MISMATCH: KXII is a primary CBS affiliate; FOX is carried on a digital subchannel (12.3). |
| US\| FOX 13 ALBUQUERQUE NM (KRQE) \| US\| FOX NETWORK | KRQE.us | NETWORK MISMATCH: KRQE is a primary CBS affiliate; FOX is carried on a digital subchannel (13.2). |