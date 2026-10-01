/**
 * The app's icon set, one family (Phosphor) at one weight, wrapped so call sites
 * stay independent of the library.
 */
import {
  ArrowLeft,
  Books,
  ChatCircleDots,
  ChatsCircle,
  ClipboardText,
  FileText,
  GitDiff,
  Heartbeat,
  House,
  Lifebuoy,
  MagnifyingGlass,
  NotePencil,
  Package,
  Question,
  Scales,
  SealCheck,
  Tray,
  TreeStructure,
  UploadSimple,
  User,
  UsersThree,
} from "@phosphor-icons/react/dist/ssr";
import type { ComponentProps } from "react";

type IconProps = ComponentProps<typeof House>;

const defaults = { size: 20, weight: "regular" } as const;

export const HomeIcon = (p: IconProps) => <House {...defaults} {...p} />;
export const HeartIcon = (p: IconProps) => <Heartbeat {...defaults} {...p} />;
export const FileIcon = (p: IconProps) => <FileText {...defaults} {...p} />;
export const ChatIcon = (p: IconProps) => <ChatCircleDots {...defaults} {...p} />;
export const SearchIcon = (p: IconProps) => <MagnifyingGlass {...defaults} {...p} />;
export const UserIcon = (p: IconProps) => <User {...defaults} {...p} />;
export const PeopleIcon = (p: IconProps) => <UsersThree {...defaults} {...p} />;
export const ArrowLeftIcon = (p: IconProps) => <ArrowLeft {...defaults} size={16} {...p} />;

// IP-SAKTI Sahayak — same family, same weight.
export const SaktiMarkIcon = (p: IconProps) => <Scales {...defaults} {...p} />;
export const AskIcon = (p: IconProps) => <Question {...defaults} {...p} />;
export const ClassifyIcon = (p: IconProps) => <TreeStructure {...defaults} {...p} />;
export const ProductIcon = (p: IconProps) => <Package {...defaults} {...p} />;
export const EscalateIcon = (p: IconProps) => <Lifebuoy {...defaults} {...p} />;
export const IncomingIcon = (p: IconProps) => <Tray {...defaults} {...p} />;
export const BriefIcon = (p: IconProps) => <ClipboardText {...defaults} {...p} />;
export const MessagesIcon = (p: IconProps) => <ChatsCircle {...defaults} {...p} />;
export const NotesIcon = (p: IconProps) => <NotePencil {...defaults} {...p} />;
export const CorpusIcon = (p: IconProps) => <Books {...defaults} {...p} />;
export const UploadIcon = (p: IconProps) => <UploadSimple {...defaults} {...p} />;
export const DraftIcon = (p: IconProps) => <GitDiff {...defaults} {...p} />;
export const ApproveIcon = (p: IconProps) => <SealCheck {...defaults} {...p} />;
