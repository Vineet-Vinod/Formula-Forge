# Monza geographic data exploration

Explored 5 September 2026. This pass changes no scene, export, collision geometry or gameplay code.

The requirement is accuracy throughout the area bounded by the actual safety barriers, with best-effort reconstruction outside. This investigation compares public services, dated imagery, engineering sources and commercial acquisition routes. It is a broad source assessment, not an exhaustive test of every geographic API or a completed survey.

## Recommendation

Use **the circuit's current engineering CAD and survey as the authority inside the barriers**, supplemented by event-specific drawings and dated ground imagery. Use **Lombardia DBGT, regional terrain data and OSM for the surroundings**. Use orthophotography to inspect and reconcile geometry where its date, accuracy and derivative-use rights are established.

Public map services alone have not demonstrated the accuracy or completeness needed to satisfy the interior requirement. If the authoritative data cannot be acquired, the honest deliverable is an explicitly provisional reconstruction with unresolved segments, not another supposedly accurate lap filled with guessed boundaries.

The working reference for this exploration is the latest documented F1 configuration available on 5 September 2026. The Italian GP is still in progress. Freeze a specific event and final document revision before implementation; temporary protection can differ from the permanent circuit. The optional configuration question remained unanswered during research.

## What was actually tested

Sample locations, longitude/latitude, were chosen near the existing model's chicanes. These are query centres, not proposed surveyed control points:

| Area | Longitude | Latitude |
| --- | ---: | ---: |
| Rettifilo, T1/T2 | 9.2822792 | 45.6245188 |
| Roggia, T4/T5 | 9.2915254 | 45.6303324 |
| Ascari, T8/T9/T10 | 9.2857818 | 45.6216999 |

The broader search envelope was `9.268,45.607,9.300,45.636` in WGS84. A bounding-box intersection establishes nearby coverage, not necessarily coverage of the entire lap. [Probe evidence](monza-geodata-evidence.json) records sampled responses and request URLs.

| Source | Observed result | Recommended use and limitation |
| --- | --- | --- |
| Lombardia AGEA 2024 orthophotography | ImageServer metadata reports 0.20 m pixels, EPSG:7791. WMS returned nonblank 1400 × 1400 images at all three chicanes, inspected directly. | Best public aerial candidate inspected for road/runoff detail. Exact local flight day and independent positional accuracy were not supplied by the queried tile catalogue. Consultation is available; derivative game-asset rights are not established. |
| Lombardia DBGT | Live road, structure and geodetic layer services respond. Road features exist in the venue envelope. Two wall representations tested returned zero features; sports-equipment polygons returned 83. | Useful open vector foundation for structures and surrounding infrastructure. Not a complete circuit barrier map. Zero results in those two wall layers do not establish absence of walls in every DBGT class. |
| Lombardia DTM 5 m | ImageServer metadata responds, with 5 m cell spacing and EPSG:32632. Dataset metadata identifies the 2015 edition. All three point-height requests timed out. | Surrounding ground candidate; actual height extraction still needs validation. Cannot resolve current kerb profiles, road crown or post-2024 road works. |
| Esri World Imagery | All three chicane metadata queries returned imagery acquired 2025-07-03, source WV02/Vantor, 0.5 m source resolution, 8.47 m reported accuracy and 0.3 m sample spacing. | Useful dated comparison. Display/sample spacing is not native resolution or positional accuracy. Do not treat the reported accuracy as a measured error at our particular chicane. |
| Esri Wayback | Official archive and metadata API documentation inspected. Archive publication dates differ from local image acquisition dates. | Useful for finding temporal changes. No full Monza archive comparison completed in this pass. |
| Airbus Pléiades Neo public archive | Spatial query for acquisitions since 2024 returned two intersecting catalogue entries: 2025-10-17 and 2026-02-21. | Promising licensed update imagery. Only catalogue records inspected, not pixels. Full-lap coverage, local shadows, local cloud and derivative rights require confirmation before ordering. |
| Google Maps / Earth / Street View | Public Monza Maps URL could not be inspected with the available web reader. Official imagery, metadata and terms documentation inspected. No authenticated Google API or panorama inspection completed. | Do not build the geometry-extraction pipeline around ordinary Google terms. No verified current Street View coverage established here. |
| Mapillary | API and image-license documentation inspected; interactive Monza view unavailable to the web reader. | Candidate ground-level evidence if dated track coverage exists. Coverage unverified. An application token would enable systematic metadata queries. |
| KartaView | Public photo API works without credentials. Broad venue-envelope sample returned 2016 roadside photos. All three sampled chicane boxes returned empty results. | Useful where dated photographs exist, but no current chicane coverage was established. This was a sample query, not an exhaustive search of every photo near the circuit. |
| MASE PST national LiDAR | Public portal and service configuration inspected. A discovered layer-config endpoint required authentication; the advertised OGC endpoint returned 404. | Remains a lead, not an acquired Monza dataset. No complete circuit coverage, relevant acquisition date or current road surface verified. Historical PST data cannot establish the resurfaced track. |
| OpenTopography | Bounding-box catalogue search worked; returned regional/global raster products, no local point-cloud entry in that response. | Coarse fallback for surroundings. A second wrapper API over the same DEM does not add resolution. |
| Comune di Monza SIT | Official city page offers aerophotogrammetric base data and mapping/download links. | Additional vector/engineering lead; underlying download not inspected in this pass. Date, coverage outside municipal boundaries and reuse terms remain to check. |
| Planet SkySat | Provider's current product/API documentation inspected; output sampled at 50 cm. | Potential paid dated scene comparison. No Monza catalogue or pixel inspection performed. |
| Vexcel / Hexagon aerial programmes | Provider documentation describes high-resolution aerial imagery and service access. | Ask for actual Monza footprints, acquisition dates, accuracy report and asset-production rights. Advertised resolution elsewhere is not verified Monza coverage. |
| Mapbox and other consumer basemaps | Mapbox documentation confirms multiple imagery suppliers, including Vantor. | Alternative delivery/viewers may repeat the same observations. They are not automatically independent checks. No local Mapbox/Bing/Azure/Cesium coverage comparison claimed. |
| Sentinel-2 / Copernicus DEM / SRTM / ALOS | Official collection descriptions inspected and/or returned in the OpenTopography query. | Background land cover and terrain only. 10 m optical or 30 m elevation grids cannot establish kerb edges or thin barrier faces. |

### Aerial samples

The AGEA WMS samples show road edges, kerbs, gravel/asphalt transitions, barrier runs and openings at the chicanes. Vegetation and shadows conceal some features. At Rettifilo, the paved escape route is visible alongside the chicane; at Roggia, the escape-road arrangement and separate outer protection are distinguishable; Ascari shows the large gravel area and its outer protection. These are observations of the supplied 2024 imagery, not assertions about the final 2026 race installation.

The images were kept in temporary local files for consultation and were not copied into the repository or game. Source: [AGEA 2024 metadata](https://www.geoportale.regione.lombardia.it/metadati?_detailSheetMetadata_WAR_gptmetadataportlet_identifier=r_lombar%3Abca4e4bb-88fe-4683-8ace-8330a5f403a6&_jsfBridgeRedirect=true&p_p_id=detailSheetMetadata_WAR_gptmetadataportlet&p_p_lifecycle=0&p_p_mode=view&p_p_state=normal), [regional viewer/service announcement](https://www.geoportale.regione.lombardia.it/home).

### The event date changes the answer

The [2026 competition notes V2, document 48](https://www.fia.com/system/files/decision-document/2026_italian_grand_prix_-_race_directors_competition_notes_v2.pdf), dated 5 September, include escape-route instructions and photographs for both initial chicanes. They also record new recessed kerbs before T1, T4 and T8, changes to the T5 gravel/asphalt area, a main-straight wall/fence change and other surface/fence updates. Therefore, an older aerial cannot stand alone as current evidence.

The [2026 map pack, document 6](https://www.fia.com/system/files/decision-document/2026_italian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf) was downloaded and its circuit-map page inspected. It establishes event layout and named/numbered locations. It is a presentation map, not the detailed engineering drawing needed to measure every barrier.

## The strongest acquisition route

The [FIA circuit drawing standard, release 5](https://api.fia.com/sites/default/files/list_of_requirements_for_the_circuit_drawing_2024.pdf) specifies metre-based CAD with separate track, paint, pit-lane, rigid-barrier, runoff, kerb, absorbing-barrier and fence layers. Track boundaries and the first protection line have 3D requirements. This is the type of source we should seek from the circuit operator/ACI, rather than tracing a simplified race map. The standard is public; Monza's completed current drawing was not located as a public download.

Ask the circuit operator/ACI for permission to use the current as-built DWG/DXF and survey in a distributed game. Request the survey coordinate system, vertical datum, acquisition date, revision history and accuracy report. Include the road edges, road surface measurements, physical track-facing barrier faces, kerb profiles, runoff surfaces and all openings. Request event-specific temporary arrangements separately.

[ACI's project record](https://trasparenza.aci.it/aci/page/110/details/297075/affidamento-servizi-tecnici-direzione-lavori-coordinamento-sicurezza-riqualificazione-alcuni-sottopassi-e-viale-ingresso-vedano-riqualificazione-pavimentazione-pista-di-f1-e-opere-idrauliche-autodromo-nazionale-monza.html) identifies MCI Infrastructures Engineering in the redevelopment work. It is a relevant engineering-data lead, not proof that downloadable as-built files exist.

[Cattura la Realtà's April 2024 case study](https://catturalarealta.it/2024/04/19/innovazione-e-precisione-il-futuro-dellarchitettura-e-dellingegneria-al-servizio-dellautodromo-di-monza/) reports a Monza laser survey. Treat this as a provider lead. Its broad marketing accuracy claims are not a substitute for an independent accuracy report, and the pre-completion date does not establish the current road. Its separate [paddock/hospitality BIM case study](https://catturalarealta.it/caso-studio-autodromo/) must not be confused with a full track survey.

If suitable current data cannot be licensed, a commissioned ground survey tied to surveyed control is the route that can satisfy strict interior accuracy. Terrestrial/mobile laser scanning plus measured barrier and kerb breaklines should be considered; controlled aerial photogrammetry can supplement exposed areas. Occluded barrier faces need ground observations. No provider has been contacted and no purchase or survey booking has been made.

## Why Google is not the production foundation

The earlier suggestion that Google could simply be traced into our game needs qualification. [Google Maps Platform terms, section 3.2.3](https://cloud.google.com/maps-platform/terms) restrict content extraction and explicitly describe prohibited roadway tracing and terrain-model creation from Elevation API values. [Google's Earth guidelines](https://about.google/intl/en-GB_ALL/brand-resource-center/products-and-services/geo-guidelines/) also restrict reconstructing models from Earth output. A normal API key does not solve the rights issue.

[Street View metadata](https://developers.google.com/maps/documentation/streetview/metadata) supplies panorama date/location/ID through an authenticated request. That identifies observations; it does not measure barrier geometry. Ground-level imagery is valuable for resolving what a feature is and whether a gap exists, but panorama coordinates should not be treated as survey control. No Google-derived geometry or imagery has been added to the project.

AGEA also needs a specific check: its metadata labels the imagery copyrighted and licensed to the region, with source distribution unavailable. Public WMS consultation is not evidence of permission to derive and distribute game meshes. DBGT and the current DTM metadata, by contrast, explicitly state CC BY 4.0. Preserve their attribution and per-layer provenance. Mapillary images have published CC BY-SA terms; those conditions and any applicable API terms must accompany their use. These are actual source-selection constraints, not reasons to stop the exploration.

## Accuracy and implementation rules

The following are proposed engineering acceptance rules, not measured results or a relaxation of the user's requirement.

1. **Define accuracy numerically before accepting a source.** Record both relative road-to-barrier accuracy and absolute geographic accuracy, separately in horizontal and vertical dimensions. A possible discussion target is 5 cm horizontal error at the physical barrier face and road boundary, with tighter vertical requirements for kerb profiles. Select the survey accordingly; do not claim this tolerance from 20 cm pixels. Report independent-check residuals and local worst cases, not only an average.
2. **Use one stable coordinate frame.** Retain the source CRS and vertical datum in the database, transform with a documented geodetic operation into local metres, and keep a small origin for the engine. EPSG:7791 regional data and EPSG:32632 DTM are not interchangeable labels. Inspect their transformations and vertical references. Do not uniformly resize the survey to force a 5,793 m lap. Use the official length as a discrepancy check and investigate the measurement convention.
3. **Model actual boundaries.** Road edges, kerb inner/outer edges, gravel/asphalt polygons, wall/Armco/absorber contact faces, fence lines and openings need their own geometries. Do not generate barriers from centreline offsets or fill unobserved chicane boundaries automatically. Fence lines are not necessarily car contact faces. Tyre/TecPro protection may sit in front of a wall.
4. **Preserve unknowns.** Every interior feature needs source ID, acquisition date, event applicability, uncertainty and validation state. Use `surveyed`, `supported by dated imagery`, `conflicting`, or `unresolved`; do not silently substitute estimates for the last two. Best-effort procedural content is acceptable outside the barriers.
5. **Use shared geometry for display and contact.** Generate Blender barriers and game collision from the same validated boundary records. Collision must preserve escape-road connectivity and genuine gaps, not merely widen the old symmetric lane clamp. Include height and barrier type so bridges and fences do not create incorrect ground-level blockers. Rendering mesh simplification must keep contact faces within the agreed numerical tolerance.
6. **Check independent observations.** Align imagery using distributed stable ground points and reserve other points for validation. Do not warp all sources until they agree or average sources that reuse the same underlying image. Elevated rails, roofs and trees can appear displaced in oblique imagery; identify the physical ground/contact feature being measured.
7. **Validate in the target game.** Overlay exported contact geometry against visible barrier faces. Drive the chicane escape routes and test both sides of gaps, barrier endpoints and approach angles. A Blender image cannot certify collision alignment or game-renderer compatibility. Keep asset accuracy checks separate from vehicle handling changes.

## Proposed next pass

Start with Rettifilo and Roggia as a source-validation pilot. They contain the reported faults and expose whether the source combination can handle openings, temporary blocks, paint, kerbs and connected runoff.

Produce a GIS evidence package with explicit road edges, barrier contact faces, openings and surface polygons; attach dates and uncertainty to every segment. Compare current circuit CAD/survey against dated aerial and ground observations. Resolve source disagreements before generating a mesh. If the required data are unavailable, return a gap map and the precise acquisition request needed to resolve each gap.

Only after that pilot meets the accuracy requirement should we replace the circuit-wide placement tables and fixed collision corridor. Surrounding buildings, woodland, service roads and terrain can proceed from open DBGT/OSM/DTM with dated aerial checks. This ordering avoids spending another environment rebuild on an unverified interior layout.

## Supporting documentation

- [DBGT metadata and CC BY 4.0](https://www.geoportale.regione.lombardia.it/web/geoportale/metadati?_detailSheetMetadata_WAR_gptmetadataportlet_identifier=r_lombar%3A0092b7ba-c697-433b-b5f2-9f9d9b8694e3&_jsfBridgeRedirect=true&p_p_id=detailSheetMetadata_WAR_gptmetadataportlet&p_p_lifecycle=0&p_p_mode=view&p_p_state=normal). Survey years vary by feature and area; database publication is not capture date.
- [DTM 5 m metadata](https://www.geoportale.regione.lombardia.it/en/metadati?_detailSheetMetadata_WAR_gptmetadataportlet_identifier=r_lombar%3Adfc98d60-5f02-4a2b-8113-5ad24cc53a9c&_jsfBridgeRedirect=true&p_p_id=detailSheetMetadata_WAR_gptmetadataportlet&p_p_lifecycle=0&p_p_mode=view&p_p_state=normal). Sources and accuracy vary; 5 m cell spacing is not 5 m vertical accuracy.
- [Esri Wayback metadata](https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/imagery/wayback-with-world-imagery-metadata) and [official API library](https://github.com/Esri/wayback-core).
- [Airbus archive query service](https://portal.intelligence-airbusds.com/arcgis/rest/services/OneAtlas/OADConstellationArchive/MapServer/2/query) and [Airbus orthorectified imagery accuracy discussion](https://www.space-solutions.airbus.com/resources/case-studies/pleiades-neo/metaverse-very-high-resolution-geospatial-data/). Native 30 cm detail does not imply 30 cm absolute accuracy.
- [Vantor 15 cm HD explanation](https://vantor.com/blog/seeing-the-world-with-complete-clarity-at-15-cm-hd-resolution/). HD is derived from native 30 cm imagery; enhancement is not new measured detail.
- [KartaView photo API](https://kartaview.org/doc/photos), [Mapillary API](https://help.mapillary.com/hc/en-us/articles/360010234680-Accessing-imagery-and-data-through-the-Mapillary-API), [Mapillary image licence](https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data).
- [MASE PST portal](https://sim.mase.gov.it/portalediaccesso/mappe/grid/c98e9e410e2b4d1d8e6aabf50212d92d), [regional LiDAR request conditions](https://www.geoportale.regione.lombardia.it/en/consultazione-e-distribuzione), [OpenTopography catalogue API](https://portal.opentopography.org/apidocs/), [Monza municipal GIS](https://www.comune.monza.it/it/page/sit).
- [Planet SkySat](https://docs.planet.com/data/imagery/skysat/), [Vexcel](https://vexceldata.com/), [Hexagon accuracy FAQ](https://hxgncontent.com/da/about/faq), [Mapbox imagery sources](https://docs.mapbox.com/data/tilesets/reference/mapbox-satellite/), [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).
