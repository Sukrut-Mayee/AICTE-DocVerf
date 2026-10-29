"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getNetwork, type NetworkEntity } from "@/lib/api";

const KIND_LABEL: Record<NetworkEntity["kind"], string> = {
  land_parcel: "Land parcel",
  trust: "Trust registration",
  photo: "Lab photo",
};
const KIND_COLOR: Record<NetworkEntity["kind"], string> = {
  land_parcel: "#b45309",
  trust: "#0369a1",
  photo: "#7c3aed",
};
const ROW = 46;
const WIDTH = 760;
const LEFT_X = 150;
const RIGHT_X = 560;

function entityLabel(entity: NetworkEntity): string {
  return `${KIND_LABEL[entity.kind]} ${entity.value}`;
}

function NetworkGraph({ entities }: { entities: NetworkEntity[] }) {
  const apps = useMemo(
    () => [...new Set(entities.flatMap((e) => e.applications.map((a) => a.app_id)))].sort(),
    [entities],
  );
  const height = Math.max(apps.length, entities.length) * ROW + 30;
  const appY = (id: string) => 30 + apps.indexOf(id) * ROW;
  const entityY = (index: number) => 30 + index * ROW;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="mx-auto w-full max-w-[820px]"
        role="img"
        aria-label="Applications linked to the land parcels, trusts and photos they share"
      >
        {entities.map((entity, index) =>
          entity.applications.map((a) => (
            <line
              key={`${entity.id}-${a.app_id}`}
              x1={LEFT_X}
              y1={appY(a.app_id)}
              x2={RIGHT_X}
              y2={entityY(index)}
              stroke={KIND_COLOR[entity.kind]}
              strokeWidth={1.5}
              opacity={0.6}
            />
          )),
        )}
        {apps.map((id) => (
          <Link key={id} href={`/officer/applications/${encodeURIComponent(id)}`}>
            <g className="cursor-pointer">
              <rect
                x={LEFT_X - 74}
                y={appY(id) - 14}
                width={74}
                height={28}
                rx={6}
                fill="#f1f5f9"
                stroke="#475569"
              />
              <text x={LEFT_X - 37} y={appY(id) + 4} textAnchor="middle" fontSize={12}>
                {id}
              </text>
            </g>
          </Link>
        ))}
        {entities.map((entity, index) => (
          <g key={entity.id}>
            <circle cx={RIGHT_X} cy={entityY(index)} r={7} fill={KIND_COLOR[entity.kind]} />
            <text x={RIGHT_X + 14} y={entityY(index) + 4} fontSize={12}>
              {entityLabel(entity)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export default function NetworkPage() {
  const [entities, setEntities] = useState<NetworkEntity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNetwork()
      .then((result) => setEntities(result.entities))
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "The network could not be loaded."),
      );
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Network</h1>
        <p className="text-sm text-muted-foreground">
          Land parcels, trust registrations and lab photos that appear in applications from more
          than one institute. Each is a preliminary indicator for the officer to review.
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load the network</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : entities === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : entities.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No shared land parcels, trusts or photos across institutes.
        </p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Applications and what they share</CardTitle>
              <CardDescription className="text-xs">
                Click an application to open it in the officer console.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <NetworkGraph entities={entities} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Shared items</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {entities.map((entity) => (
                <div key={entity.id} className="rounded-md border p-3 text-sm">
                  <p className="font-medium" style={{ color: KIND_COLOR[entity.kind] }}>
                    {entityLabel(entity)}
                  </p>
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {entity.applications.map((a) => (
                      <li key={`${entity.id}-${a.app_id}`}>
                        <Link
                          href={`/officer/applications/${encodeURIComponent(a.app_id)}`}
                          className="font-medium text-sky-800 underline"
                        >
                          {a.app_id}
                        </Link>
                        {a.institute_name ? ` · ${a.institute_name}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
