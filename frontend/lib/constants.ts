// Mirrors the LEGAL_AREAS enum in backend/prompts.py. Kept hard-coded here
// (and validated server-side) so the dropdown renders before /api/me has
// resolved a token. The backend rejects values not in this list.
export const LEGAL_AREAS = [
  "Contract Law",
  "Employment Law",
  "Intellectual Property",
  "Corporate / M&A",
  "Regulatory / Compliance",
  "Personal Injury / Tort",
  "Real Estate / Property",
  "Data Privacy / GDPR",
  "Criminal Law",
  "Family Law",
  "Other",
] as const;

// Common-law and major civil-law jurisdictions whose case law our agents
// know reasonably well. Backend doesn't enforce this list — any non-empty
// string is accepted — so users can type a free-form country if they pick
// "Other". Order roughly: Anglo, North America, Asia-Pacific, Africa, EU.
export const COUNTRIES = [
  "United Kingdom",
  "United States",
  "Canada",
  "Australia",
  "New Zealand",
  "Ireland",
  "India",
  "Pakistan",
  "Bangladesh",
  "Singapore",
  "Hong Kong",
  "South Africa",
  "Kenya",
  "Nigeria",
  "Ghana",
  "Tanzania",
  "Uganda",
  "Zimbabwe",
  "Zambia",
  "European Union",
  "Other",
] as const;

export const DEFAULT_COUNTRY = "United Kingdom";

export const JUDGE_PLACEHOLDER =
  "_Awaiting final judgment. Refine the arguments above, then pronounce judgment when ready._";
export const STRATEGY_PLACEHOLDER =
  "_The strategic memo will be generated alongside the final judgment._";

export const EMPTY_STATE = {
  plaintiff: "",
  defense: "",
  expert: "",
  judge: JUDGE_PLACEHOLDER,
  scores: [],
  strategy: STRATEGY_PLACEHOLDER,
  summary: "",
};
