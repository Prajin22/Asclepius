"use client";

import { useApi } from "@carebridge/api-client/react";
import { errorMessage, useT } from "@carebridge/i18n";
import type { ProductProfile } from "@carebridge/shared-types";
import { Button } from "@carebridge/ui";
import { Flask } from "@phosphor-icons/react/dist/ssr";
import { useState } from "react";
import { useDemoMode } from "../SaktiShell";
import { SAMPLE_PRODUCT } from "./overview";

/**
 * Demo mode only: adds one clearly synthetic product to the signed-in user's
 * own list, through the ordinary API, when they ask for it. Never seeded,
 * never shown outside demo mode, and labelled "DEMO DATA" wherever it appears.
 */
export function SampleProductButton({ onCreated }: { onCreated: (product: ProductProfile) => void }) {
  const api = useApi();
  const t = useT();
  const demo = useDemoMode();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (!demo) return null;
  return (
    <span className="inline-flex flex-col items-center gap-1.5">
      <Button
        variant="secondary"
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            onCreated(await api.products.create(SAMPLE_PRODUCT));
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
        disabled={busy}
      >
        <Flask size={18} aria-hidden />
        {busy ? t("ui.demo.loadingSample") : t("ui.demo.loadSample")}
      </Button>
      {error ? (
        <span role="alert" className="text-small text-danger">
          {errorMessage(t, error)}
        </span>
      ) : null}
    </span>
  );
}
