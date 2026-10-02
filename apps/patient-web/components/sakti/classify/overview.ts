"use client";

import { useQuery } from "@carebridge/api-client/react";
import type { ClassificationSummary, ProductFields, ProductProfile } from "@carebridge/shared-types";
import type { ProductState } from "../ui";

/**
 * Where a product's classification stands, derived from what the API already
 * returns — no new endpoint, no stored "state". An open session decides first
 * (in progress, requires information, awaiting confirmation); otherwise a
 * confirmed classification; otherwise none. A rejected result leaves the
 * product unclassified: rejecting never picks another category.
 */
export function productState(product: ProductProfile, history: ClassificationSummary[] | undefined): ProductState {
  if (product.open_session_id) {
    const open = history?.find((s) => s.id === product.open_session_id);
    if (open?.status === "requires_information") return "requires_information";
    if (open?.status === "determined") return "awaiting_confirmation";
    return "in_progress";
  }
  return product.confirmed_classification ? "confirmed" : "not_classified";
}

export interface ProductOverview {
  product: ProductProfile;
  /** Newest first, as the API returns it. */
  history: ClassificationSummary[];
  state: ProductState;
}

/** The user's products with each one's classification history and derived state. */
export function useProductOverview() {
  return useQuery(async (api) => {
    const products = await api.products.list();
    const histories = await Promise.all(products.map((p) => api.products.classifications(p.id)));
    return products.map<ProductOverview>((product, i) => ({
      product,
      history: histories[i],
      state: productState(product, histories[i]),
    }));
  });
}

/** Synthetic demo products carry this in their name, and are labelled wherever they appear. */
export const DEMO_MARK = "DEMO DATA";
export const isDemoProduct = (p: Pick<ProductProfile, "name">) => p.name.includes(DEMO_MARK);

/**
 * The one sample product demo mode can add, on request, to the signed-in
 * user's own list. Every value is visibly synthetic: generic ingredient names,
 * no real formulation, no classical text, nothing that reads as a legal fact.
 */
export const SAMPLE_PRODUCT: ProductFields = {
  name: `Sample herbal tablet (${DEMO_MARK})`,
  intended_use: "Synthetic demonstration entry for trying the classifier. Not a real product.",
  dosage_form: "Tablet",
  administration_route: "oral",
  ingredients: [
    { name: "Sample ingredient A", part_used: "Root", quantity: "250 mg" },
    { name: "Sample ingredient B", part_used: "Leaf", quantity: "100 mg" },
  ],
  preparation_method: "Synthetic demonstration text. It describes no real process.",
  classical_reference: null,
  extract_description: null,
  standardization_description: null,
  markers: [],
  notes: `${DEMO_MARK}: added by "Load a sample product". Synthetic values only.`,
  text_language: "en",
};
