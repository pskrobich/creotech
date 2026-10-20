# STAC Satellite Metadata Catalog

A Python microservice that receives satellite product metadata from two providers, converts it to
[STAC](https://stacspec.org/) Items and stores it in PostgreSQL/PostGIS, so it can be searched by area,
time, cloud cover and processing level.

| Mission      | Provider       | Metadata format | Sample                       |
|--------------|----------------|-----------------|------------------------------|
| `SKY_SHIELD` | SkyIsNoLimit   | JSON            | `samples/SkyIsNoLimit.json`  |
| `SPACE_EYE`  | SpaceIsNoLimit | XML             | `samples/SpaceIsNoLimit.xml` |

Stack: Python 3.12, FastAPI, pystac, PostgreSQL 18 + PostGIS 3.6, psycopg 3, Alembic, Docker Compose.

## Running

```bash
docker compose up --build
```

This starts the database (`localhost:5432`) and the API (`http://localhost:8000`). On startup the API
runs the database migrations. Interactive API docs: http://localhost:8000/docs

To stop it and remove the stored data: `docker compose down -v`.

## Example requests

Ingest the SkyIsNoLimit sample (JSON):

```bash
curl -i -X PUT http://localhost:8000/v1/ingest \
  -H "Content-Type: application/json" \
  --data-binary @- <<'EOF'
{
  "acquisition_metadata": {
    "provider_id": "SkyIsNoLimit",
    "mission_name": "SKY_SHIELD",
    "satellite_id": "SKY_SHIELD_03",
    "scene_identifier": "SKY_SHIELD_20260824_091522_L1C_POL",
    "capture_timestamp_utc": "2026-08-24T09:15:22.451Z",
    "orbit": {
      "path": 142,
      "row": 33,
      "direction": "descending"
    }
  },
  "product_characteristics": {
    "processing_level": "L1C",
    "sensor_type": "optical_multispectral",
    "metrics": {
      "cloud_cover_percentage": 14.2,
      "snow_cover_percentage": 0.0,
      "sun_azimuth_deg": 154.32,
      "sun_elevation_deg": 48.71
    }
  },
  "spatial_extent": {
    "coordinate_system": "EPSG:4326",
    "bounding_box": {
      "min_longitude": 20.912,
      "min_latitude": 52.185,
      "max_longitude": 21.245,
      "max_latitude": 52.398
    },
    "geometry_geojson": {
      "type": "Polygon",
      "coordinates": [[
        [20.912, 52.185],
        [21.245, 52.185],
        [21.245, 52.398],
        [20.912, 52.398],
        [20.912, 52.185]
      ]]
    }
  },
  "data_deliverables": {
    "image_bands": {
      "red": "https://data.skyisnolimit.com/store/2026/08/24/SKY_SHIELD_B04.tif",
      "green": "https://data.skyisnolimit.com/store/2026/08/24/SKY_SHIELD_B03.tif",
      "blue": "https://data.skyisnolimit.com/store/2026/08/24/SKY_SHIELD_B02.tif",
      "nir": "https://data.skyisnolimit.com/store/2026/08/24/SKY_SHIELD_B08.tif"
    },
    "thumbnail": "https://data.skyisnolimit.com/store/2026/08/24/SKY_SHIELD_thumb.png"
  }
}
EOF
```

Ingest the SpaceIsNoLimit sample (XML):

```bash
curl -i -X PUT http://localhost:8000/v1/ingest \
  -H "Content-Type: application/xml" \
  --data-binary @- <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<GranuleMetadata xmlns="http://spaceisnolimit.com/schemas/metadata/v2">
  <HeaderInfo>
    <Provider>SpaceIsNoLimit</Provider>
    <Mission>SPACE_EYE</Mission>
    <SpacecraftID>SE-02</SpacecraftID>
    <GranuleID>SE02_L2A_20260824T104500_N001</GranuleID>
  </HeaderInfo>
  <TemporalCoverage>
    <StartTimeUTC>2026-08-24T10:45:00Z</StartTimeUTC>
    <StopTimeUTC>2026-08-24T10:45:18Z</StopTimeUTC>
  </TemporalCoverage>
  <ProductQuality>
    <ProcessingLevel>L2A</ProcessingLevel>
    <CloudCoveragePercentage>4.85</CloudCoveragePercentage>
    <DataQualityStatus>PASSED</DataQualityStatus>
  </ProductQuality>
  <GeometricProperties>
    <CRS>EPSG:32634</CRS>
    <FootprintWKT>POLYGON((500000 5800000, 609780 5800000, 609780 5690220, 500000 5690220, 500000 5800000))</FootprintWKT>
    <GlobalBBOX>
      <WestBoundLongitude>19.981</WestBoundLongitude>
      <EastBoundLongitude>21.615</EastBoundLongitude>
      <SouthBoundLatitude>51.355</SouthBoundLatitude>
      <NorthBoundLatitude>52.342</NorthBoundLatitude>
    </GlobalBBOX>
  </GeometricProperties>
  <RasterFiles>
    <Band index="1" name="B04_RED" resolution_m="10">
      <URL>s3://space-eye-products/2026/L2A/SE02_20260824_B04.tif</URL>
    </Band>
    <Band index="2" name="B08_NIR" resolution_m="10">
      <URL>s3://space-eye-products/2026/L2A/SE02_20260824_B08.tif</URL>
    </Band>
    <OverviewFile type="QUICKLOOK">
      <URL>s3://space-eye-products/2026/L2A/SE02_20260824_QL.jpg</URL>
    </OverviewFile>
  </RasterFiles>
</GranuleMetadata>
EOF
```

The response is `201` the first time and `204` when the same product is sent again. You can also send
the files from `samples/`, e.g. `--data-binary @samples/SkyIsNoLimit.json`.

Search by area, time, cloud cover and processing level:

```bash
curl -G http://localhost:8000/v1/search \
  --data-urlencode "bbox=20,51,23,53" \
  --data-urlencode "start_datetime=2026-08-24T00:00:00Z" \
  --data-urlencode "end_datetime=2026-08-25T00:00:00Z" \
  --data-urlencode "max_cloud_coverage=10" \
  --data-urlencode "processing_level=L2A"
```

This returns the SPACE_EYE item only: the SKY_SHIELD item has 14.2 % cloud cover and level `L1C`.

## API

Both endpoints return `503` when the database is unavailable.

### `PUT /v1/ingest`

The body is the raw metadata file from the provider. The `Content-Type` header selects the format:
`application/json` for SkyIsNoLimit, `application/xml` or `text/xml` for SpaceIsNoLimit.

| Status | Meaning                                                                      |
|--------|------------------------------------------------------------------------------|
| 201    | the item was stored                                                          |
| 204    | an item with the same collection and id existed and was replaced             |
| 400    | the content is not recognized as metadata of a supported provider            |
| 415    | unsupported `Content-Type`                                                   |
| 422    | the provider is recognized, but the metadata is invalid (the reason is in `detail`) |

Sending the same product again is safe; it replaces the stored item.

### `GET /v1/search`

| Parameter            | Description                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| `bbox`               | `minx,miny,maxx,maxy` in WGS84 degrees; items whose footprint intersects it |
| `start_datetime`     | items whose acquisition time ends at or after this time                     |
| `end_datetime`       | items whose acquisition time starts at or before this time                  |
| `max_cloud_coverage` | `eo:cloud_cover` less than or equal to the value (0-100)                    |
| `processing_level`   | exact `processing:level`                                                    |
| `limit`              | page size, 1-1000 (default 10)                                              |
| `offset`             | number of items to skip (default 0)                                         |

All parameters are optional. Dates must include a timezone. The response is a JSON array of STAC
Items, newest first. Invalid parameters return 422.

## How it works

- **Adapters** (`app/adapters`): one per provider. Each one recognizes its format and maps it to a STAC
  Item with the Electro-Optical (`eo:cloud_cover`) and Processing (`processing:level`) extensions.
  The item is then validated against the official STAC JSON schemas.
- **SPACE_EYE footprint**: the provider gives it in the coordinate system from the `CRS` element
  (`EPSG:32634`, in metres, in the sample); it is reprojected to longitude/latitude (WGS84), as STAC
  requires. The item's bbox is computed from the footprint, because the `GlobalBBOX` in
  the sample file does not cover it (it says 19.981-21.615°E, while the footprint spans 21.0-22.61°E).
- **Time**: SKY_SHIELD has a single capture time, SPACE_EYE an acquisition window. Both are stored as a
  time range, so the `/search` time filter works the same way for both.
- **Storage**: table `stac_items` (Alembic migration in `migrations/`) keeps the full STAC Item as
  `jsonb` plus indexed columns used by the search filters (PostGIS geometry, time range, cloud cover,
  processing level).
- **Ingestion is synchronous**: the provider gets the result immediately and can resend a rejected
  file.

## Tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

- `tests/adapters`: unit tests of the provider adapters (mapping and invalid metadata).
- `tests/api`: tests of the HTTP API against a real PostGIS database. They check results only through
  the API, e.g. a stored item is checked through `/search`. A database outage is simulated to check the `503` response.

Docker must be running: the tests start a PostGIS container (testcontainers) and run the migrations
on it.
