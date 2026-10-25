# TreeSearch - OFO ground reference explorer

**A friendlier way into forest ground-reference and drone data, and a way for the people working with it to find each other.**

[Live app (WE DONT HAVE A LINK RN)](LINK_HERE) · Built at UN Reboot the Earth Hackathon @ UC Davis, October 2026

---

## Why we built this

The [Open Forest Observatory (OFO)](https://openforestobservatory.org) maintains a rich catalog of forest data: hand-measured tree plots on the ground, and the drone missions flown over them. It is valuable data, but getting the data you need from it can take a lot of digging.

Before writing any code, we talked with professionals who work with this data and asked what they wished their data navigation tool could do. Two things came up again and again: **better ways to search and filter**, and **a way to find out who else is working on the same ground**. This project is our answer to both.

Underneath it all is a bigger goal: the more easily researchers, surveyors, and land managers can reach the data and each other, the better equipped they are to reduce wildfire risk across the West Coast.

We kept OFO's data exactly as published. What we changed is how you move through it.

## What it does

### 1. Explore the data on a map, with filters that actually connect

- **One map, three layers of data.** Ground-measured trees (dot size shows height, color shows species), plot boundaries, and drone mission footprints, over a color-coded wildfire hazard background.
- **Tree filters:** species, live/dead, project, trunk diameter (DBH), height, ground survey year, and the wildfire hazard class of the plot.
- **Drone mission filters:** flight date, front and side image overlap, and altitude.
- **Place filters:** pan to a county (or limit everything to it), and zoom straight to a specific plot.
- **Everything stays in sync.** One filtered result drives the map, the counts, and the tables (trees, plots, missions). A filter on drone missions narrows the plots and trees they cover, and a filter on trees narrows the missions that remain.
- **Wildfire hazard context.** A background layer from the USFS Wildfire Hazard Potential map, so a plot's surroundings are visible at a glance, plus a filter by hazard class.

### 2. Connect with others through the forum

Researchers, survey crews, and land managers can post about work they have done or plan to do: who they are, what they are surveying, which plot, the status of the work, and optional contact info. The goal is simple: make it easy for people doing similar work to find each other.

- Browse posts and filter by status, state, or county.
- Pick a plot or county on the map and the posts for that area appear in a panel beside it.

**Changing the look.** Colors and fonts live in `.streamlit/config.toml`.

## Data

| What | Source | Used for |
|---|---|---|
| Ground-reference plots and trees, drone missions | [OFO data catalog](https://openforestobservatory.org) (three GeoPackage files) | The map, filters, and tables |
| Wildfire Hazard Potential 2023 | [USFS Research Data Archive, RDS-2015-0047-4](https://www.fs.usda.gov/rds/archive/catalog/RDS-2015-0047-4) | Hazard background and per-plot hazard class |
| County boundaries | [US Census cartographic boundary files](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html) | County lookup and filtering |

Expected files in `data/`: `ofo_ground-reference_plots.gpkg`, `ofo_ground-reference_trees.gpkg`, `ofo_drone-missions.gpkg`, the Census county zip, and the generated `plot_whp.csv`, `whp_overlay.png`, and `whp_overlay.json`.

> OFO data carries per-plot licenses. If you redistribute or build on it, check the license that applies to the data you use.

## How it's built

**Python**, **Streamlit** (app and interface), **GeoPandas** and **pyogrio** (reading and joining the geospatial data), **Plotly** (the map), **rasterio** (one-time hazard preprocessing only), and **git**.

```
TreeSearch.py       the map page: filters, map, tables, post panel
pages/1_Forum.py    the forum page: write and browse posts
data_loader.py      reads and cleans the data, links plots to missions and counties
filters.py          the filter logic: plain functions, no UI code
forum.py            forum storage and helpers
prep_whp.py         one-time hazard layer preprocessing
.streamlit/         theme (colors and fonts)
data/               datasets and generated files
```

A few design choices worth knowing about:

- **Filters are plain functions** (a table goes in, a filtered table comes out), separate from the interface, so they are easy to test and extend.
- **The map, counts, and tables all read from the same filtered result,** so they can never disagree.
- **Heavy work happens once.** Plots are linked to drone missions and counties by a spatial join at load time, and the hazard layer is pre-rendered, so filtering stays fast.

## Known limitations

We would rather you hear these from us:

- **Hazard class is a relative rating, not a forecast.** It comes from a 270 m grid, so a plot takes the class of the cell it sits in. The USFS notes it is not an explicit map of wildfire risk.
- **The plots are research sites, not a representative sample** of western forests. Numbers describe those sites only.
- **Shrub density isn't available.** Shrubs were recorded in only 2 of 287 plots, because most surveys only measured trees above a size cutoff. We left it out rather than show a misleading map.
- **Roughly half of the drone missions don't overlap any ground plot,** so they don't appear. Everything on the map is tied to ground-measured data.
- **The forum is a proof of concept.** Posts are stored in a simple file, with no accounts or moderation, and contact info is shown publicly. On the hosted demo, posts may reset when the app restarts.
- **The posts panel follows filters, not scroll-zooming.** The map doesn't report to the app where you've panned or zoomed by hand, so the panel responds to the county, plot, and filters you pick.
- **Many fields are incomplete.** About half of the trees have no recorded height, so range filters include a "keep missing values" option.

## What's (possibly) next

1. **A standardized intake form** that lets people add new data to the map, with a way to keep the map up to date as OFO's data changes.
2. **A sturdier forum:** permanent storage, accounts, moderation, and posts shown directly on the map at their plots.
3. **More fire-relevant measures,** such as tree and standing-dead density, compared fairly across plots that used different size cutoffs.

## Team
Anthony Perry II · [Nadia Bourne](https://www.linkedin.com/in/nadia-bourne/) · Viviana Cruz · Troy Mireku

## Thank you

To the professionals during the hackathon who took the time to tell us what they wished existed, to the USFS and the US Census Bureau for open data, and to the United Nations - Reboot the Earth hackathon for the opportunity.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/25826c7d-26f9-428f-8988-02de8cad0a1b" />

## License

Data is subject to its original licenses (see [Data](#data)).
