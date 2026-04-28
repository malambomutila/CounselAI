import { useEffect, useState } from "react";
import { COUNTRIES, DEFAULT_COUNTRY, LEGAL_AREAS } from "@/lib/constants";

interface InputCardProps {
  busy: boolean;
  initial?: { case: string; area: string; position: string; country: string };
  onAnalyse: (payload: {
    case: string;
    area: string;
    position: string;
    country: string;
  }) => void;
}

export function InputCard({ busy, initial, onAnalyse }: InputCardProps) {
  const [caseText, setCase] = useState(initial?.case ?? "");
  const [area, setArea] = useState<string>(initial?.area ?? LEGAL_AREAS[0]);
  const [position, setPosition] = useState(initial?.position ?? "");

  // Country is a dropdown of well-known jurisdictions. If the user (or a
  // restored conversation) supplies a value not in the list, drop into
  // "Other" and surface the free-text input pre-populated with it.
  const initialCountry = initial?.country ?? DEFAULT_COUNTRY;
  const isKnown = (COUNTRIES as readonly string[]).includes(initialCountry);
  const [countryDropdown, setCountryDropdown] = useState<string>(
    isKnown ? initialCountry : "Other"
  );
  const [countryOther, setCountryOther] = useState<string>(
    isKnown ? "" : initialCountry
  );

  useEffect(() => {
    const nextCase = initial?.case ?? "";
    const nextArea = initial?.area ?? LEGAL_AREAS[0];
    const nextPosition = initial?.position ?? "";
    const nextCountry = initial?.country ?? DEFAULT_COUNTRY;
    const nextKnown = (COUNTRIES as readonly string[]).includes(nextCountry);

    setCase(nextCase);
    setArea(nextArea);
    setPosition(nextPosition);
    setCountryDropdown(nextKnown ? nextCountry : "Other");
    setCountryOther(nextKnown ? "" : nextCountry);
  }, [initial]);

  const country =
    countryDropdown === "Other" ? countryOther.trim() : countryDropdown;

  const submit = () => {
    if (busy || !caseText.trim() || !position.trim() || !country) return;
    onAnalyse({ case: caseText, area, position, country });
  };

  return (
    <div className="card-padded mb-9">
      <label className="block mb-1 text-[11px] uppercase tracking-[0.1em] text-ink-subtle font-semibold">
        Case Description
      </label>
      <textarea
        rows={6}
        className="w-full px-3 py-2 border border-hairline rounded-sm text-sm font-sans"
        placeholder="Paste the case facts, incident details, or current filing here…"
        value={caseText}
        onChange={(e) => setCase(e.target.value)}
        disabled={busy}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
        <div>
          <label className="block mb-1 text-[11px] uppercase tracking-[0.1em] text-ink-subtle font-semibold">
            Legal Area
          </label>
          <select
            className="w-full px-3 py-2 border border-hairline rounded-sm text-sm bg-white"
            value={area}
            onChange={(e) => setArea(e.target.value)}
            disabled={busy}
          >
            {LEGAL_AREAS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block mb-1 text-[11px] uppercase tracking-[0.1em] text-ink-subtle font-semibold">
            Country (Jurisdiction)
          </label>
          <select
            className="w-full px-3 py-2 border border-hairline rounded-sm text-sm bg-white"
            value={countryDropdown}
            onChange={(e) => setCountryDropdown(e.target.value)}
            disabled={busy}
            title="Whose laws should the agents apply?"
          >
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {countryDropdown === "Other" && (
            <input
              type="text"
              className="w-full mt-2 px-3 py-2 border border-hairline rounded-sm text-sm"
              placeholder="Enter country (e.g. Botswana)"
              value={countryOther}
              onChange={(e) => setCountryOther(e.target.value)}
              disabled={busy}
            />
          )}
        </div>

        <div>
          <label className="block mb-1 text-[11px] uppercase tracking-[0.1em] text-ink-subtle font-semibold">
            Your Position
          </label>
          <input
            type="text"
            className="w-full px-3 py-2 border border-hairline rounded-sm text-sm"
            placeholder="e.g. Defending the accused"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            disabled={busy}
          />
        </div>
      </div>

      <p className="text-[11px] text-ink-subtle mt-3 italic">
        Agents will cite real precedents from the chosen jurisdiction&apos;s
        case law, with links where available.
      </p>

      <div className="flex justify-end mt-5">
        <button
          type="button"
          className="cta-primary"
          onClick={submit}
          disabled={busy || !caseText.trim() || !position.trim() || !country}
        >
          {busy ? "Analysing…" : "Analyse My Case"}
        </button>
      </div>
    </div>
  );
}
