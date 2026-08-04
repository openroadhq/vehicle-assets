# Vehicle catalog ↔ image-manifest slug drift

- Catalog: `740` bundled entries
- Manifest: `2398` vehicles · `15` aliases · `1088` generation families
- Manifest source: `openroadhq/vehicle-assets@main/manifest.json (GitHub connector)`
- Slugs absent from `vehicles ∪ aliases ∪ generations`: **169**
- Verified semantic generation drifts: **1**
- Inventory rows: **170** (169 literal union misses + 1 semantic drift; RS6 is already a generation-family key)
- Drifts with no same-make manifest candidate (asset required): **26**

## Drift inventory

| Catalog slug | Catalog years | Suggested manifest key | Confidence | Reason |
|---|---:|---|---|---|
| `abarth/595` | 2016–2023 | — | asset required | absent from manifest union; no same-make candidate |
| `acura/zdx-type-s` | 2024–2025 | `acura/zdx` | review | absent from manifest union |
| `alfa-romeo/8c` | 2008–2010 | `alfa-romeo/8c-competizione` | review | absent from manifest union |
| `aston-martin/v8-vantage` | 2006–2017 | `aston-martin/vantage-v8-2005` | review | absent from manifest union |
| `audi/rs-q3` | 2020– | `audi/q3` | review | absent from manifest union |
| `audi/rs4-b7` | 2006–2008 | `audi/rs4-2007` | review | absent from manifest union |
| `audi/rs6` | 2020– | `audi/rs6-avant` | verified | semantic generation drift |
| `audi/sq8` | 2020– | — | asset required | absent from manifest union; no same-make candidate |
| `bmw/i4-m50` | 2022– | `bmw/i4` | review | absent from manifest union |
| `bmw/i5-m60` | 2024– | `bmw/i5` | review | absent from manifest union |
| `bmw/m135i` | 2019– | `bmw/1-series-2011` | review | absent from manifest union |
| `bmw/m240i` | 2022– | `bmw/2-series` | review | absent from manifest union |
| `bmw/m3-e46` | 2001–2006 | `bmw/m3-2001` | verified | absent from manifest union |
| `bmw/m3-e92` | 2008–2013 | `bmw/m3-2008` | review | absent from manifest union |
| `bmw/m440i` | 2021– | `bmw/4-series` | review | absent from manifest union |
| `bmw/m5-cs` | 2021–2022 | `bmw/m5-2018` | review | absent from manifest union |
| `bmw/m5-e60` | 2005–2010 | `bmw/m5-2006` | review | absent from manifest union |
| `bmw/m850i` | 2019– | `bmw/8-series` | review | absent from manifest union |
| `buick/grand-national` | 1984–1987 | — | asset required | absent from manifest union; no same-make candidate |
| `cadillac/ct4-v` | 2020– | `cadillac/ct4-2020` | review | absent from manifest union |
| `cadillac/ct4-v-blackwing` | 2022– | `cadillac/ct4-blackwing-2020` | verified | absent from manifest union |
| `cadillac/ct5-v` | 2020– | `cadillac/ct5-2020` | review | absent from manifest union |
| `cadillac/ct5-v-blackwing` | 2022– | `cadillac/ct5-blackwing-2020` | review | absent from manifest union |
| `cadillac/escalade-iq` | 2025– | `cadillac/escalade` | review | absent from manifest union |
| `chevrolet/blazer-ev-ss` | 2024– | `chevrolet/blazer` | review | absent from manifest union |
| `chevrolet/camaro-z28` | 2014–2015 | `chevrolet/camaro-2016` | review | absent from manifest union |
| `chevrolet/chevelle-ss` | 1968–1972 | — | asset required | absent from manifest union; no same-make candidate |
| `chevrolet/corvette-c4-zr-1` | 1990–1995 | `chevrolet/corvette-zr1-1990` | review | absent from manifest union |
| `chevrolet/corvette-c5` | 1997–2004 | `chevrolet/corvette-1997` | review | absent from manifest union |
| `chevrolet/corvette-c5-z06` | 2001–2004 | `chevrolet/corvette-z06-1997` | review | absent from manifest union |
| `chevrolet/corvette-c6` | 2005–2013 | `chevrolet/corvette-2005` | review | absent from manifest union |
| `chevrolet/corvette-c6-z06` | 2006–2013 | `chevrolet/corvette-z06-2005` | review | absent from manifest union |
| `chevrolet/corvette-c6-zr1` | 2009–2013 | `chevrolet/corvette-zr1-2005` | review | absent from manifest union |
| `chevrolet/corvette-c7-z06` | 2015–2019 | `chevrolet/corvette-z06-2014` | review | absent from manifest union |
| `chevrolet/corvette-c7-zr1` | 2019–2019 | `chevrolet/corvette-zr1-2020` | review | absent from manifest union |
| `chevrolet/corvette-e-ray` | 2024– | `chevrolet/corvette` | review | absent from manifest union |
| `chevrolet/corvette-stingray` | 2020– | `chevrolet/corvette` | review | absent from manifest union |
| `chevrolet/silverado-2500hd` | 2001– | `chevrolet/silverado-1999` | review | absent from manifest union |
| `chevrolet/silverado-ev` | 2024– | `chevrolet/silverado-2014` | review | absent from manifest union |
| `chevrolet/silverado-trail-boss` | 2019– | `chevrolet/silverado-2014` | review | absent from manifest union |
| `chevrolet/silverado-zr2` | 2022– | `chevrolet/silverado-2014` | review | absent from manifest union |
| `chevrolet/tahoe-rst` | 2018– | `chevrolet/tahoe-2015` | review | absent from manifest union |
| `cupra/formentor` | 2021– | — | asset required | absent from manifest union; no same-make candidate |
| `cupra/leon` | 2021– | — | asset required | absent from manifest union; no same-make candidate |
| `de-tomaso/pantera` | 1971–1992 | — | asset required | absent from manifest union; no same-make candidate |
| `dodge/challenger-demon-170` | 2023–2023 | `dodge/challenger-demon-2018` | review | absent from manifest union |
| `dodge/challenger-hellcat-redeye` | 2019–2023 | `dodge/challenger-redeye-2019` | review | absent from manifest union |
| `dodge/challenger-scat-pack` | 2015–2023 | `dodge/challenger` | review | absent from manifest union |
| `dodge/charger-hellcat-redeye` | 2021–2023 | `dodge/charger-hellcat-2015` | review | absent from manifest union |
| `dodge/charger-scat-pack` | 2015–2023 | `dodge/charger` | review | absent from manifest union |
| `dodge/neon-srt-4` | 2003–2005 | `dodge/neon-srt4-2003` | review | absent from manifest union |
| `dodge/viper-rt-10` | 1992–1995 | `dodge/viper-1992` | review | absent from manifest union |
| `dodge/viper-srt-10` | 2003–2010 | `dodge/viper-zb-2003` | review | absent from manifest union |
| `ferrari/360` | 1999–2005 | `ferrari/360-modena` | review | absent from manifest union |
| `ferrari/458` | 2010–2015 | `ferrari/458-italia` | review | absent from manifest union |
| `ferrari/550` | 1996–2001 | `ferrari/550-maranello` | review | absent from manifest union |
| `ferrari/599` | 2006–2012 | `ferrari/599-gto` | review | absent from manifest union |
| `ferrari/sf90` | 2020– | `ferrari/sf90-xx` | review | absent from manifest union |
| `ford/edge-st` | 2019–2024 | `ford/edge` | review | absent from manifest union |
| `ford/f-150-raptor-r` | 2023– | `ford/f-150-raptor` | review | absent from manifest union |
| `ford/f-250` | 2023– | `ford/f-250-super-duty` | review | absent from manifest union |
| `ford/f-350` | 1999– | — | asset required | absent from manifest union; no same-make candidate |
| `ford/gt` | 2017–2022 | `ford/ford-gt-2017` | review | absent from manifest union |
| `ford/mustang-dark-horse` | 2024– | `ford/mustang-mach-1-2021` | review | absent from manifest union |
| `ford/mustang-fox-body` | 1979–1993 | `ford/mustang-fox-1979` | review | absent from manifest union |
| `ford/mustang-gt` | 2024– | `ford/mustang` | review | absent from manifest union |
| `ford/mustang-gtd` | 2025– | `ford/mustang` | review | absent from manifest union |
| `ford/mustang-mach-e-gt` | 2021– | `ford/mustang-mach-1-2021` | review | absent from manifest union |
| `ford/svt-lightning` | 1999–2004 | `ford/f-150-lightning-1999` | review | absent from manifest union |
| `gmc/canyon-at4x` | 2023– | `gmc/canyon` | review | absent from manifest union |
| `gmc/hummer-ev` | 2022– | `gmc/hummer-ev-suv` | review | absent from manifest union |
| `gmc/sierra-at4` | 2019– | `gmc/sierra-1500` | review | absent from manifest union |
| `gmc/sierra-denali` | 2001– | `gmc/sierra-1500-1999` | review | absent from manifest union |
| `hyundai/i20-n` | 2021–2024 | — | asset required | absent from manifest union; no same-make candidate |
| `hyundai/i30-n` | 2018– | — | asset required | absent from manifest union; no same-make candidate |
| `infiniti/g35` | 2003–2007 | `infiniti/g35-sedan-2003` | review | absent from manifest union |
| `jaguar/project-8` | 2018–2019 | `jaguar/xe-project-8-2018` | review | absent from manifest union |
| `jeep/wrangler-rubicon-392` | 2021– | `jeep/wrangler-392-2021` | review | absent from manifest union |
| `koenigsegg/one-1` | 2014–2015 | `koenigsegg/agera-one1` | review | absent from manifest union |
| `lamborghini/huracan-evo` | 2019–2024 | `lamborghini/huracan` | review | absent from manifest union |
| `land-rover/defender-octa` | 2025– | `land-rover/defender-2020` | review | absent from manifest union |
| `land-rover/range-rover` | 2022– | `land-rover/range-rover-l460-2022` | review | absent from manifest union |
| `lexus/gx-470` | 2003–2009 | `lexus/gx-2003` | review | absent from manifest union |
| `lexus/gx-550` | 2024– | `lexus/gx` | review | absent from manifest union |
| `lexus/is-300` | 2001–2005 | `lexus/is-2000` | review | absent from manifest union |
| `lexus/is-500` | 2022– | `lexus/is` | review | absent from manifest union |
| `lexus/ls-400` | 1990–2000 | `lexus/ls-1990` | review | absent from manifest union |
| `lexus/ls-500` | 2018– | `lexus/ls` | review | absent from manifest union |
| `lexus/lx-570` | 2008–2021 | `lexus/lx-2008` | review | absent from manifest union |
| `lexus/lx-600` | 2022– | `lexus/lx` | review | absent from manifest union |
| `lexus/nx-350` | 2022– | `lexus/nx` | review | absent from manifest union |
| `lexus/rc-350` | 2015– | `lexus/rc` | review | absent from manifest union |
| `lexus/rx-500h` | 2023– | `lexus/rx` | review | absent from manifest union |
| `lexus/sc-300` | 1992–2000 | — | asset required | absent from manifest union; no same-make candidate |
| `lexus/tx-350` | 2024– | `lexus/tx` | review | absent from manifest union |
| `lotus/evora-gt` | 2020–2021 | `lotus/evora` | review | absent from manifest union |
| `maserati/grecale-trofeo` | 2023– | `maserati/grecale` | review | absent from manifest union |
| `maserati/levante-trofeo` | 2019–2023 | `maserati/levante` | review | absent from manifest union |
| `mazda/mazda3-turbo` | 2021– | `mazda/mazda3` | review | absent from manifest union |
| `mazda/rx-7-fc` | 1986–1992 | `mazda/rx-7-1986` | review | absent from manifest union |
| `mercedes-amg/a45-s` | 2020– | `mercedes-benz/a45-amg-2019` | review | absent from manifest union |
| `mercedes-amg/c43` | 2017–2022 | `mercedes-benz/c-class-2015` | review | absent from manifest union |
| `mercedes-amg/c63` | 2015–2021 | `mercedes-benz/c63-amg` | review | absent from manifest union |
| `mercedes-amg/c63-w204` | 2008–2015 | `mercedes-benz/c63-amg-2008` | review | absent from manifest union |
| `mercedes-amg/c63-w205` | 2015–2021 | `mercedes-benz/c63-amg` | review | absent from manifest union |
| `mercedes-amg/cla45` | 2020– | `mercedes-benz/cla45-amg-2019` | review | absent from manifest union |
| `mercedes-amg/e53` | 2019– | `mercedes-benz/e-class-2016` | review | absent from manifest union |
| `mercedes-amg/e55` | 2003–2006 | `mercedes-benz/e-class-2003` | review | absent from manifest union |
| `mercedes-amg/e63` | 2017–2023 | `mercedes-benz/e63-s-amg-2017` | review | absent from manifest union |
| `mercedes-amg/g63` | 2019– | `mercedes-benz/g63-amg` | review | absent from manifest union |
| `mercedes-amg/glc63` | 2018–2023 | `mercedes-benz/glc63-amg-2017` | review | absent from manifest union |
| `mercedes-amg/gle53` | 2021– | `mercedes-benz/gle` | review | absent from manifest union |
| `mercedes-amg/gle63` | 2021– | `mercedes-benz/gle63-amg` | review | absent from manifest union |
| `mercedes-amg/gt` | 2024– | `mercedes-benz/amg-gt` | review | absent from manifest union |
| `mercedes-amg/gt-63` | 2019– | `mercedes-benz/amg-gt-63-4-door-2018` | review | absent from manifest union |
| `mercedes-amg/gt-black-series` | 2021–2021 | `mercedes-benz/amg-gt-black-series-2020` | review | absent from manifest union |
| `mercedes-amg/gt-r` | 2017–2021 | `mercedes-benz/amg-gt-r-2017` | review | absent from manifest union |
| `mercedes-amg/one` | 2023– | — | asset required | absent from manifest union; no same-make candidate |
| `mercedes-amg/s63` | 2023– | `mercedes-benz/s-class` | review | absent from manifest union |
| `mercedes-amg/sl63` | 2022– | `mercedes-benz/sl` | review | absent from manifest union |
| `mercedes-benz/g550` | 2019– | `mercedes-benz/g-class` | review | absent from manifest union |
| `mitsubishi/evo-ix` | 2005–2007 | `mitsubishi/lancer-evolution-ix-2005` | review | absent from manifest union |
| `mitsubishi/evo-vi` | 1999–2001 | `mitsubishi/lancer-evolution-vi-1999` | review | absent from manifest union |
| `mitsubishi/evo-viii` | 2003–2005 | `mitsubishi/lancer-evolution-viii-2003` | review | absent from manifest union |
| `mitsubishi/evo-x` | 2008–2015 | `mitsubishi/lancer-evolution-x-2008` | review | absent from manifest union |
| `mitsubishi/pajero` | 1989–2021 | `mitsubishi/pajero-evolution-1997` | review | absent from manifest union |
| `nissan/patrol` | 1989– | — | asset required | absent from manifest union; no same-make candidate |
| `nissan/sentra-sr` | 2020– | `nissan/sentra` | review | absent from manifest union |
| `nissan/silvia-s13` | 1989–1994 | `nissan/silvia-s15-1999` | review | absent from manifest union |
| `nissan/silvia-s14` | 1993–1998 | `nissan/silvia-s15-1999` | review | absent from manifest union |
| `pagani/zonda` | 1999–2017 | `pagani/zonda-r` | review | absent from manifest union |
| `pininfarina/battista` | 2022– | — | asset required | absent from manifest union; no same-make candidate |
| `porsche/718-boxster` | 2017– | `porsche/boxster` | review | absent from manifest union |
| `porsche/718-cayman` | 2017– | `porsche/cayman` | review | absent from manifest union |
| `porsche/718-gt4-rs` | 2022–2024 | `porsche/cayman-gt4-2019` | review | absent from manifest union |
| `porsche/718-spyder` | 2020–2023 | `porsche/boxster-spyder` | review | absent from manifest union |
| `porsche/911-carrera-s` | 2020– | `porsche/911-turbo-s` | review | absent from manifest union |
| `porsche/911-gts` | 2022– | `porsche/911` | review | absent from manifest union |
| `porsche/macan-gts` | 2022– | `porsche/macan-2014` | review | absent from manifest union |
| `porsche/panamera-turbo` | 2017–2023 | `porsche/panamera-turbo-s-2016` | review | absent from manifest union |
| `porsche/taycan-turbo` | 2020– | `porsche/taycan-turbo-s-2019` | review | absent from manifest union |
| `ram/1500-limited` | 2016– | `ram/1500-2011` | review | absent from manifest union |
| `ram/1500-rebel` | 2015– | `ram/1500-2011` | review | absent from manifest union |
| `ram/1500-rho` | 2025– | `ram/1500` | review | absent from manifest union |
| `ram/srt-10` | 2004–2006 | `ram/1500-2011` | review | absent from manifest union |
| `renault/clio-rs` | 2013–2019 | `renault/clio-williams-1993` | review | absent from manifest union |
| `renault/megane-rs` | 2019–2023 | — | asset required | absent from manifest union; no same-make candidate |
| `rimac/nevera` | 2021– | — | asset required | absent from manifest union; no same-make candidate |
| `rolls-royce/cullinan` | 2019– | `rolls-royce/cullinan-black-badge` | review | absent from manifest union |
| `skoda/octavia-rs` | 2021– | — | asset required | absent from manifest union; no same-make candidate |
| `subaru/22b-sti` | 1998–1999 | `subaru/impreza-22b-sti-1998` | review | absent from manifest union |
| `subaru/baja` | 2003–2006 | — | asset required | absent from manifest union; no same-make candidate |
| `subaru/legacy-gt` | 2005–2009 | `subaru/legacy-2005` | review | absent from manifest union |
| `suzuki/swift-sport` | 2006– | — | asset required | absent from manifest union; no same-make candidate |
| `tesla/model-3-performance` | 2024– | `tesla/model-3` | review | absent from manifest union |
| `toyota/aristo` | 1991–2004 | — | asset required | absent from manifest union; no same-make candidate |
| `toyota/chaser` | 1996–2001 | — | asset required | absent from manifest union; no same-make candidate |
| `toyota/cressida` | 1989–1992 | — | asset required | absent from manifest union; no same-make candidate |
| `toyota/crown` | 2023– | — | asset required | absent from manifest union; no same-make candidate |
| `toyota/fj-cruiser` | 2007–2014 | — | asset required | absent from manifest union; no same-make candidate |
| `toyota/gr-yaris` | 2020– | `toyota/yaris-2007` | review | absent from manifest union |
| `toyota/grand-highlander` | 2024– | — | asset required | absent from manifest union; no same-make candidate |
| `toyota/hilux` | 1989– | — | asset required | absent from manifest union; no same-make candidate |
| `toyota/land-cruiser-100` | 1998–2007 | `toyota/land-cruiser-1998` | review | absent from manifest union |
| `toyota/land-cruiser-200` | 2008–2021 | `toyota/land-cruiser-2008` | review | absent from manifest union |
| `toyota/land-cruiser-300` | 2021– | `toyota/land-cruiser-2008` | review | absent from manifest union |
| `toyota/land-cruiser-80` | 1990–1997 | `toyota/land-cruiser-1991` | review | absent from manifest union |
| `toyota/supra-mk3` | 1986–1992 | `toyota/supra-1993` | review | absent from manifest union |
| `toyota/supra-mk4` | 1993–1998 | `toyota/supra-1993` | review | absent from manifest union |
| `volkswagen/arteon-r` | 2020–2024 | `volkswagen/arteon-2019` | review | absent from manifest union |

## Ready-to-paste verified alias map

Only hand-verified mappings are included below. Targets marked `review` above are deliberately excluded until image-checked.

```json
{
  "audi/rs6": "audi/rs6-avant",
  "bmw/m3-e46": "bmw/m3-2001",
  "cadillac/ct4-v-blackwing": "cadillac/ct4-blackwing-2020"
}
```


