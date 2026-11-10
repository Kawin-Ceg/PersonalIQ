import type { Dimension, Level, Source } from "@/types/api";

export const DIMENSION_LABEL: Record<Dimension | "fit", string> = {
  durability: "Durability",
  quality: "Quality",
  price: "Low price",
  value: "Value for money",
  fit: "Fits your preferences",
};

export const LEVEL_LABEL: Record<Level, string> = { high: "High", medium: "Medium", low: "Low" };

/** Plain-language provenance shown next to every fact. */
export const SOURCE_LABEL: Record<Source, string> = {
  user_stated: "You told us",
  uploaded: "From your spending",
  feedback: "From your feedback",
  observed: "From what you did",
  inferred: "PersonalIQ's guess",
  default: "Not set",
};

export const SCORE_LABEL: Record<"quality" | "value" | "price" | "durability" | "fit", string> = {
  quality: "Quality",
  value: "Value for money",
  price: "Price",
  durability: "Durability",
  fit: "Fits your preferences",
};
