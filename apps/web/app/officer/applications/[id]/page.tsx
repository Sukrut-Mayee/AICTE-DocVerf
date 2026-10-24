"use client";

import { useParams } from "next/navigation";

import { ApplicationWorkspace } from "@/components/officer/application-workspace";

export default function ApplicationPage() {
  const params = useParams<{ id: string }>();
  const appId = Array.isArray(params.id) ? params.id[0] : params.id;
  return <ApplicationWorkspace appId={appId} />;
}
