"use client";

import { useParams } from "next/navigation";
import { ClassificationFlow } from "@/components/sakti/classify/ClassificationFlow";

export default function ClassificationPage() {
  const { id } = useParams<{ id: string }>();
  return <ClassificationFlow id={id} />;
}
