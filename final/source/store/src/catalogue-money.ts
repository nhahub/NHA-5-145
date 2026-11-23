import type { Currency } from "./catalogue.js";

export interface Money {
  readonly amount: string;
  readonly currency: Currency;
}

export function money(amount: string): Money {
  if (!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(amount))
    throw new TypeError(
      "Money amount must be a non-negative decimal with at most two places",
    );
  return { amount, currency: "EGP" };
}

function minorUnits(value: Money): bigint {
  const [whole, fraction = ""] = value.amount.split(".");
  return BigInt(whole!) * 100n + BigInt(fraction.padEnd(2, "0"));
}

export function compareMoney(left: Money, right: Money): number {
  if (left.currency !== right.currency)
    throw new TypeError("Money currencies must match");
  const difference = minorUnits(left) - minorUnits(right);
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}
