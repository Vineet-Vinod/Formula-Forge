# Added circuits

Nineteen layouts were built from OpenStreetMap raceway geometry and Copernicus GLO-90 elevations sampled on 2026-11-04. The driving length is the mapped plan, scaled to a published length only when the two already agreed within 1.5%. Shoulders use nearby OSM barriers where a vertex exists and a venue default where one does not.

Suzuka is the only figure-eight. Its pit straight is raised to a 6.2 m deck when the 90 m surface model cannot see the bridge. The lower road is left on the sampled height.

Walls are continuous, including pit entry. That closure is for the game. Widths are typical asphalt figures, not a white-line survey. There is no lidar and no cockpit capture in this pass. GLO-90 is a surface model: street circuits can still carry roof and tree height, and the stated vertical uncertainty is 8 m there and 5 m on permanent circuits.

| Circuit | Mapped m | Published m | Scale | Relief m | Turns found | Buildings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bahrain | 5422.5 | 5412 | 0.9981 | 19.7 | 13 | 45 |
| Jeddah | 6192.6 | 6174 | 0.9970 | 3.9 | 24 | 7 |
| Australia | 5307.6 | 5278 | 0.9944 | 6.9 | 20 | 21 |
| Japan | 5809.6 | 5807 | 0.9996 | 50.9 | 19 | 64 |
| China | 5460.8 | 5451 | 0.9982 | 8.7 | 12 | 26 |
| Canada | 4364.1 | 4361 | 0.9993 | 12.7 | 15 | 13 |
| Monaco | 3317.2 | 3337 | 1.0060 | 57.1 | 20 | 92 |
| Austria | 4303.0 | 4318 | 1.0035 | 67.7 | 11 | 10 |
| Spa | 6998.7 | 7004 | 1.0008 | 99.8 | 21 | 35 |
| Zandvoort | 4255.9 | 4259 | 1.0007 | 7.8 | 16 | 6 |
| Baku | 5971.0 | 6003 | 1.0054 | 36.9 | 17 | 214 |
| Malaysia | 5547.7 | 5543 | 0.9992 | 21.0 | 16 | 23 |
| Singapore | 4956.8 | 4940 | 0.9966 | 20.0 | 17 | 32 |
| COTA | 5504.3 | 5513 | 1.0016 | 21.9 | 18 | 22 |
| Las Vegas | 6210.2 | 6201 | 0.9985 | 24.5 | 14 | 65 |
| Turkey | 5347.9 | 5338 | 0.9981 | 35.3 | 15 | 8 |
| Portimao | 4661.4 | 4653 | 0.9982 | 27.9 | 16 | 11 |
| Buddh | 5137.1 | 5141 | 1.0008 | 13.2 | 16 | 1 |
| Hockenheim | 4567.2 | 4574 | 1.0015 | 9.2 | 13 | 41 |

Hanoi is not in the game. OpenStreetMap's circuit relation there is two separate pieces, about 2.6 km and 2.3 km, and the roads around My Dinh do not join them into the published 5.607 km lap. Closing that gap would mean inventing roughly 600 m of circuit.

Source notes for each venue are in `Attribution/Sources/<slug>/provenance.json`. Contact surfaces are regenerated with `make circuits`.
