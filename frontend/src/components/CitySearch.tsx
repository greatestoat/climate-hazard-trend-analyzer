import { useId, useState } from "react";
import { useCitySearch } from "../hooks/useCitySearch";
import type { CityResult } from "../types/api";

interface Props {
  selected: CityResult | null;
  onSelect: (c: CityResult | null) => void;
}

export function CitySearch({ selected, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const { results, loading, error } = useCitySearch(selected ? "" : query);
  const listId = useId();

  const pick = (c: CityResult) => {
    onSelect(c);
    setOpen(false);
    setQuery("");
  };

  if (selected) {
    return (
      <div className="flex items-center justify-between rounded-md border border-white/20 bg-ink-soft px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{selected.name}</p>
          <p className="truncate text-xs text-paper/60">
            {[selected.admin1, selected.country].filter(Boolean).join(", ")} · {selected.latitude.toFixed(2)}, {selected.longitude.toFixed(2)}
          </p>
        </div>
        <button onClick={() => onSelect(null)} className="ml-2 rounded px-2 py-1 text-xs text-amber hover:bg-white/10">
          Change
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <input
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label="Search for a city"
        value={query}
        placeholder="Search a city, e.g. Hyderabad"
        onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if (e.key === "Enter" && open && results[active]) { e.preventDefault(); pick(results[active]); }
          else if (e.key === "Escape") setOpen(false);
        }}
        className="w-full rounded-md border border-white/20 bg-ink-soft px-3 py-2 text-sm text-paper placeholder:text-paper/40"
      />
      {open && query.trim().length >= 2 && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-line bg-surface text-ink shadow-lg">
          {loading && <li className="px-3 py-2 text-sm text-muted">Searching…</li>}
          {error && <li className="px-3 py-2 text-sm text-ember">{error}</li>}
          {!loading && !error && results.length === 0 && <li className="px-3 py-2 text-sm text-muted">No cities match “{query.trim()}”.</li>}
          {results.map((c, i) => (
            <li key={`${c.id}-${c.latitude}-${c.longitude}`} role="option" aria-selected={i === active}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={() => pick(c)}
                className={`block w-full px-3 py-2 text-left text-sm ${i === active ? "bg-mist" : ""}`}
              >
                <span className="font-semibold">{c.name}</span>
                <span className="text-muted"> {[c.admin1, c.country].filter(Boolean).join(", ")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
