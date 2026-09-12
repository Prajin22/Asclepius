/**
 * The app's icon set, one family (Phosphor) at one weight, wrapped so call sites
 * stay independent of the library.
 */
import { ArrowLeft, ChatCircleDots, FileText, Heartbeat, House, MagnifyingGlass, User } from "@phosphor-icons/react/dist/ssr";
import type { ComponentProps } from "react";

type IconProps = ComponentProps<typeof House>;

const defaults = { size: 20, weight: "regular" } as const;

export const HomeIcon = (p: IconProps) => <House {...defaults} {...p} />;
export const HeartIcon = (p: IconProps) => <Heartbeat {...defaults} {...p} />;
export const FileIcon = (p: IconProps) => <FileText {...defaults} {...p} />;
export const ChatIcon = (p: IconProps) => <ChatCircleDots {...defaults} {...p} />;
export const SearchIcon = (p: IconProps) => <MagnifyingGlass {...defaults} {...p} />;
export const UserIcon = (p: IconProps) => <User {...defaults} {...p} />;
export const ArrowLeftIcon = (p: IconProps) => <ArrowLeft {...defaults} size={16} {...p} />;
