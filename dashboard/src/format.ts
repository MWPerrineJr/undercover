export const label = (value: string) =>
  value.replaceAll("_", " ").replace("sign off", "sign-off");
export const money = (value: string | number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(value),
  );
