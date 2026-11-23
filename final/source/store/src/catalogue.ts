export const categories = ["shoes", "clothing", "bags", "electronics"] as const;

export type Category = (typeof categories)[number];
export type ProductSort = "cheapest" | "newest";
export type Currency = "EGP";

import { compareMoney, type Money } from "./catalogue-money.js";
export { money, compareMoney, type Money } from "./catalogue-money.js";

export interface Product {
  id: string;
  category: Category;
  nameAr: string;
  nameEn: string;
  type: string;
  price: Money;
  sizes: readonly string[];
  colors: readonly string[];
  available: boolean;
  addedAt: string;
  features: readonly string[];
  suitableFor: readonly string[];
  wearPosition: "upper" | "lower" | null;
}

export interface ProductConstraints {
  category: Category;
  query?: string;
  type?: string;
  minPrice?: Money;
  maxPrice?: Money;
  size?: string;
  color?: string;
  availability?: boolean;
  sort?: ProductSort;
}

function normalized(value: string): string {
  return value.trim().toLocaleLowerCase("en");
}

export function filterProductRecords(
  records: readonly Product[],
  constraints: ProductConstraints,
): Product[] {
  const query =
    constraints.query === undefined ? undefined : normalized(constraints.query);
  const matches = records.filter((product) => {
    if (product.category !== constraints.category) return false;
    if (query !== undefined && query !== "") {
      const searchable = [
        product.nameAr,
        product.nameEn,
        product.type,
        ...product.colors,
      ]
        .join(" ")
        .toLocaleLowerCase("en");
      if (!searchable.includes(query)) return false;
    }
    if (
      constraints.type !== undefined &&
      normalized(product.type) !== normalized(constraints.type)
    )
      return false;
    if (
      constraints.minPrice !== undefined &&
      compareMoney(product.price, constraints.minPrice) < 0
    )
      return false;
    if (
      constraints.maxPrice !== undefined &&
      compareMoney(product.price, constraints.maxPrice) > 0
    )
      return false;
    if (
      constraints.size !== undefined &&
      !product.sizes.some(
        (size) => normalized(size) === normalized(constraints.size!),
      )
    )
      return false;
    if (
      constraints.color !== undefined &&
      !product.colors.some(
        (color) => normalized(color) === normalized(constraints.color!),
      )
    )
      return false;
    if (
      constraints.availability !== undefined &&
      product.available !== constraints.availability
    )
      return false;
    return true;
  });

  if (constraints.sort === "cheapest") {
    matches.sort(
      (left, right) =>
        compareMoney(left.price, right.price) ||
        left.id.localeCompare(right.id),
    );
  } else if (constraints.sort === "newest") {
    matches.sort(
      (left, right) =>
        right.addedAt.localeCompare(left.addedAt) ||
        left.id.localeCompare(right.id),
    );
  }
  return matches;
}

export interface ShoeConstraints {
  type?: string;
  minPrice?: Money;
  maxPrice?: Money;
}
