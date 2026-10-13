Leaflet 1.9.4, vendored for the field pack (stage A1b).

Source        : npm package "leaflet@1.9.4" (published 2023-05-18; the 2.x line is only alpha), dist/leaflet.js, dist/leaflet.css and LICENSE, copied UNMODIFIED.
                Checked on 2026-10-13: byte-identical to the files of the package in frontend/node_modules (and so to the package-lock entry), and to a fresh `npm pack leaflet@1.9.4`.
Licence       : BSD-2-Clause, see LICENSE in this folder (Copyright (c) 2010-2023 Volodymyr Agafonkin, 2010-2011 CloudMade). The copyright notice also stays in the header of leaflet.js.
sha256        : leaflet.js  db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a
                leaflet.css a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6
                LICENSE     53e8dc25862014e4324741ca18fbe3611e11d42ef69f59f86ea8c5389647d4cb
How it is used: scripts/build_field_pack.py puts leaflet.js and leaflet.css INSIDE the one HTML page. The page loads nothing from a CDN. The only network requests of the page are the map tiles.
                The one change made at build time: the three url(images/...) references of leaflet.css (layer switch icons, default marker icon) are replaced by `none`, because this page uses
                neither control and must not ask for any other file. The files in this folder are not edited.
To update      : copy the new files from the npm package, check the sha256 against the registry (`npm pack leaflet@<version>`), pin an exact version that is at least two weeks old, and update this file.
