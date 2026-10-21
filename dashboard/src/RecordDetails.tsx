import type { BusinessRecord, Json } from "./types";

import { label, money } from "./format";

function Value({ value }: Readonly<{ value: Json }>) {
  if (value === null) return <span>None</span>;
  if (Array.isArray(value))
    return value.length ? (
      <ul className="record-list">
        {value.map((item, index) => (
          <li key={index}>
            <Value value={item} />
          </li>
        ))}
      </ul>
    ) : (
      <span>None</span>
    );
  if (typeof value === "object") return <RecordDetails record={value} />;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  return <span>{String(value)}</span>;
}

export function RecordDetails({
  record,
}: Readonly<{ record: BusinessRecord }>) {
  return (
    <dl className="record">
      {Object.entries(record).map(([key, value]) => (
        <div key={key}>
          <dt>{label(key)}</dt>
          <dd>
            {typeof value === "number" &&
            /(amount|paid|cost|max|deductible|limit)$/.test(key) ? (
              <span className="identifier">{money(value)}</span>
            ) : (
              <Value value={value} />
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
