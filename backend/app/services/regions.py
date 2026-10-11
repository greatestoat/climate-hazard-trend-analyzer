"""Geographic region representation.

* City  -> a single point at the geocoded coordinates.
* Box   -> an N x N grid of cell-centre points (default 3 x 3). Open-Meteo is
          queried for every point and the daily maximum temperatures are averaged
          (ignoring missing points) into one regional series. The 95th-percentile
          threshold is then computed on that area-mean series.
"""
from app.schemas import BBoxRegion, CityRegion


def region_points(region: CityRegion | BBoxRegion, grid: int) -> tuple[list[tuple[float, float]], str, str]:
    """Returns (points, stable region_key, human description)."""
    if isinstance(region, CityRegion):
        lat, lon = round(region.latitude, 2), round(region.longitude, 2)
        return [(lat, lon)], f"pt:{lat:.2f}:{lon:.2f}:era5", "Single grid point at the city coordinates"
    pts = []
    for i in range(grid):
        lat = region.south + (i + 0.5) * (region.north - region.south) / grid
        for j in range(grid):
            lon = region.west + (j + 0.5) * (region.east - region.west) / grid
            pts.append((round(lat, 3), round(lon, 3)))
    key = f"bbox:{region.south:.2f}:{region.west:.2f}:{region.north:.2f}:{region.east:.2f}:g{grid}:era5"
    return pts, key, f"Mean of a {grid}x{grid} grid of cell-centre points inside the bounding box"
