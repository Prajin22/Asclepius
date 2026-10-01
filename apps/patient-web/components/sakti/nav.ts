/**
 * IP-SAKTI Sahayak's information architecture: who sees which destinations.
 *
 * One entry per screen. A screen is a placeholder until the phase that builds
 * it flips `available`; nothing may be shown as working before it does. Phase 2
 * built the curator's four screens; every other screen is still a placeholder.
 */
import type { SaktiRole } from "@carebridge/shared-types";
import type { ComponentProps, ReactNode } from "react";
import {
  ApproveIcon,
  AskIcon,
  BriefIcon,
  ClassifyIcon,
  CorpusIcon,
  DraftIcon,
  EscalateIcon,
  IncomingIcon,
  MessagesIcon,
  NotesIcon,
  PeopleIcon,
  ProductIcon,
  UploadIcon,
} from "@/components/icons";

type Icon = (props: ComponentProps<typeof AskIcon>) => ReactNode;

/** Every IP-SAKTI screen. The key names its text under `pages.<key>` in the catalogue. */
export type SaktiPage =
  | "ask"
  | "classify"
  | "myProduct"
  | "escalate"
  | "incoming"
  | "brief"
  | "messages"
  | "notes"
  | "corpus"
  | "upload"
  | "drafts"
  | "approve"
  | "facilitators";

export interface SaktiPageInfo {
  /** Which `pages.<key>.points.*` lines describe what the screen will do. */
  points: readonly ("one" | "two" | "three")[];
  /** Whether `pages.<key>.note` exists. */
  note?: boolean;
  /** False until the phase that builds the screen. */
  available: boolean;
}

export const SAKTI_PAGES: Record<SaktiPage, SaktiPageInfo> = {
  ask: { points: ["one", "two", "three"], available: false },
  classify: { points: ["one", "two"], available: false },
  myProduct: { points: ["one", "two", "three"], note: true, available: false },
  escalate: { points: ["one", "two"], available: false },
  incoming: { points: ["one", "two"], available: false },
  brief: { points: ["one"], available: false },
  messages: { points: ["one"], available: false },
  notes: { points: ["one"], available: false },
  corpus: { points: ["one", "two"], available: true },
  upload: { points: ["one"], available: true },
  drafts: { points: ["one"], available: true },
  approve: { points: ["one"], available: true },
  facilitators: { points: ["one"], available: false },
};

export interface SaktiNavItem {
  href: string;
  page: SaktiPage;
  /** Catalogue key of the short label. */
  label: string;
  Icon: Icon;
}

/** Each role's destinations, in order. The first is where the role lands. */
export const SAKTI_NAV: Record<SaktiRole, readonly SaktiNavItem[]> = {
  user: [
    { href: "/ask", page: "ask", label: "nav.ask", Icon: AskIcon },
    { href: "/classify", page: "classify", label: "nav.classify", Icon: ClassifyIcon },
    { href: "/my-product", page: "myProduct", label: "nav.myProduct", Icon: ProductIcon },
    { href: "/escalate", page: "escalate", label: "nav.escalate", Icon: EscalateIcon },
  ],
  facilitator: [
    { href: "/facilitator", page: "incoming", label: "nav.incoming", Icon: IncomingIcon },
    { href: "/facilitator/brief", page: "brief", label: "nav.brief", Icon: BriefIcon },
    { href: "/facilitator/messages", page: "messages", label: "nav.messages", Icon: MessagesIcon },
    { href: "/facilitator/notes", page: "notes", label: "nav.notes", Icon: NotesIcon },
  ],
  curator: [
    { href: "/curator", page: "corpus", label: "nav.corpus", Icon: CorpusIcon },
    { href: "/curator/upload", page: "upload", label: "nav.upload", Icon: UploadIcon },
    { href: "/curator/drafts", page: "drafts", label: "nav.drafts", Icon: DraftIcon },
    { href: "/curator/approve", page: "approve", label: "nav.approve", Icon: ApproveIcon },
  ],
  admin: [{ href: "/admin", page: "facilitators", label: "nav.facilitators", Icon: PeopleIcon }],
};
