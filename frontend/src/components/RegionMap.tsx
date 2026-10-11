import { useState } from "react";
import { CircleMarker, MapContainer, Rectangle, TileLayer, useMapEvents } from "react-leaflet";
import type { LatLngExpression, LatLngTuple } from "leaflet";
import type { FormState } from "../lib/request";

interface Props {
  bbox: FormState["bbox"];
  center: LatLngExpression;
  onBoxChange: (bbox: FormState["bbox"]) => void;
}

function validBounds(bbox: FormState["bbox"]): [[number, number], [number, number]] | null {
  const { south, west, north, east } = bbox;
  const values = [south, west, north, east].map(Number);
  if (values.some((v) => !Number.isFinite(v)) || [south, west, north, east].some((v) => v.trim() === "")) return null;
  const [s, w, n, e] = values;
  return s >= -90 && n <= 90 && w >= -180 && e <= 180 && s < n && w < e ? [[s, w], [n, e]] : null;
}

function BoxClickHandler({ onPick }: { onPick: (point: LatLngTuple) => void }) {
  useMapEvents({ click: (event) => onPick([event.latlng.lat, event.latlng.lng]) });
  return null;
}

export function RegionMap({ bbox, center, onBoxChange }: Props) {
  const [firstCorner, setFirstCorner] = useState<LatLngTuple | null>(null);
  const bounds = validBounds(bbox);

  const pickCorner = (point: LatLngTuple) => {
    if (!firstCorner) {
      setFirstCorner(point);
      return;
    }
    const south = Math.min(firstCorner[0], point[0]);
    const west = Math.min(firstCorner[1], point[1]);
    const north = Math.max(firstCorner[0], point[0]);
    const east = Math.max(firstCorner[1], point[1]);
    onBoxChange({ ...bbox, south: south.toFixed(3), west: west.toFixed(3), north: north.toFixed(3), east: east.toFixed(3) });
    setFirstCorner(null);
  };

  return (
    <div className="overflow-hidden rounded-lg border border-white/15">
      <div role="application" aria-label="Map for selecting a region">
        <MapContainer center={center} zoom={4} scrollWheelZoom className="h-56 w-full">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <BoxClickHandler onPick={pickCorner} />
          {bounds && <Rectangle bounds={bounds} pathOptions={{ color: "#e9a23b", weight: 2, fillOpacity: 0.16 }} />}
          {firstCorner && <CircleMarker center={firstCorner} radius={5} pathOptions={{ color: "#e9a23b", fillColor: "#e9a23b", fillOpacity: 1 }} />}
        </MapContainer>
      </div>
      <p className="bg-ink-soft px-3 py-2 text-xs text-paper/70" aria-live="polite">
        {firstCorner ? "Now click the opposite corner to finish your box." : "Click two opposite corners to select a box. You can also enter coordinates below."}
      </p>
    </div>
  );
}
