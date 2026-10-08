# LGU nursery list and the species of the system (round 15a)

**Source:** the nursery list of the LGU, **handwritten**. Names were read from the handwriting and some are uncertain (marked `(?)`). **Quantities are unknown**: the table says which species the nursery has, not how many seedlings.
Files: `data/processed/nursery_stock.csv` (listed_name, matched_species_id, match_note, in_system), made by `pipeline/species_extras.py`. No species was added to the system.
The API shows `in_nursery` (true or false), `nursery_match` ("yes" or "partial") and the matched list names on `GET /species` and `GET /species/{id}`.

## Matched (14 names, 14 species)
| Listed name | System species | Note |
|---|---|---|
| Guyabano | Guyabano | same common name |
| Cacao | Cacao | same common name |
| Kasoy (Kassoy) | Kasoy | listed as Kassoy |
| Duhat | Duhat | same common name |
| Narra | Narra | same common name |
| Fire Tree | Fire Tree | same common name |
| Rambutan | Rambutan | same common name |
| Sampalok | Sampalok | same common name |
| Avocado | Avocado | same common name |
| Talisay | Talisay | same common name |
| Coconut | Coconut | same common name |
| Calamansi | Calamansi | same common name |
| Banaba | Banaba | same common name |
| Mabolo | Kamagong | matched **only because** our Kamagong has the scientific name *Diospyros blancoi*, which is the mabolo tree; checked in `species_clean.csv` |

## Partial match (1)
| Listed name | System species | Note |
|---|---|---|
| Kape | Robusta (Coffee) | only Robusta (*Coffea canephora*) is in the system; the kind of coffee in the nursery is not stated. `in_nursery` is true for Robusta with `nursery_match` "partial". |

## Not matched (18)
| Listed name | Why |
|---|---|
| Banyan | **not matched**: possible Weeping Fig, confirm |
| Durian, Tui/Tuai (*Bischofia javanica*), Kamatsile, Suha (*Citrus maxima*), Banyaw, Luntibani, Balitbitan, Eugenia, Camansi, Atis, Lagundi, Alibangbang, Dungon | not in the system |
| Morong(?), Casimjas/Castanas(?), Caupiyus(?) | not in the system; the handwritten name is uncertain |
| Nymp Tree | probably Neem; not in the system |

## Limits
- 15 of the 45 species are in the nursery (14 matched, plus Robusta as a partial match). The nursery list says nothing about how many seedlings are ready or when.
- The handwriting was read by the project team; the uncertain names should be confirmed with the nursery staff.
- The nursery table does not change any score or plan; it is information for the planners.
