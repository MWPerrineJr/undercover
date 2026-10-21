export const label = (value: string) => value.replaceAll("_", " ");
export const money = (value: string | number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(value),
  );
