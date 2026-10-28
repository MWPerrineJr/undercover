export const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .replace("sign off", "sign-off")
    .replace("left for handler", "left for a handler");
export const money = (value: string | number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(value),
  );
export const claimState = (claim: {
  status: string;
  left_for_handler: boolean;
}) => (claim.left_for_handler ? "left_for_handler" : claim.status);
