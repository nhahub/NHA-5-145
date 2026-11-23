export const categories = ["shoes", "clothing", "bags", "electronics"] as const;

export type Category = (typeof categories)[number];
export type ProductSort = "cheapest" | "newest";
export type Currency = "EGP";

export interface Money {
  readonly amount: string;
  readonly currency: Currency;
}

const MONEY_AMOUNT = /^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/;

export function money(amount: string): Money {
  if (!MONEY_AMOUNT.test(amount))
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

type ProductSeed = Omit<
  Product,
  "category" | "price" | "features" | "suitableFor" | "wearPosition"
> & {
  price: string;
  features?: readonly string[];
  suitableFor?: readonly string[];
  wearPosition?: Product["wearPosition"];
};

const shoeSeeds: readonly ProductSeed[] = [
  {
    id: "shoe-01",
    nameAr: "عدّاء النيل",
    nameEn: "Nile Runner",
    type: "running",
    price: "1450",
    sizes: ["40", "41", "42"],
    colors: ["blue", "black"],
    available: true,
    addedAt: "2026-01-02",
  },
  {
    id: "shoe-02",
    nameAr: "خطوة سريعة",
    nameEn: "Quick Step",
    type: "running",
    price: "1750",
    sizes: ["41", "42", "43"],
    colors: ["white", "red"],
    available: true,
    addedAt: "2026-01-08",
    features: ["cushioned"],
    suitableFor: ["daily_workouts", "road_running"],
  },
  {
    id: "shoe-03",
    nameAr: "نسمة الصباح",
    nameEn: "Morning Breeze",
    type: "running",
    price: "2000",
    sizes: ["39", "40", "42"],
    colors: ["gray", "green"],
    available: true,
    addedAt: "2026-01-15",
  },
  {
    id: "shoe-04",
    nameAr: "ماراثون القاهرة",
    nameEn: "Cairo Marathon",
    type: "running",
    price: "2450",
    sizes: ["42", "43", "44"],
    colors: ["black", "orange"],
    available: true,
    addedAt: "2026-02-01",
    features: ["cushioned", "grip"],
    suitableFor: ["daily_workouts", "road_running"],
  },
  {
    id: "shoe-05",
    nameAr: "جري الصحراء",
    nameEn: "Desert Run",
    type: "running",
    price: "2800",
    sizes: ["41", "43", "45"],
    colors: ["sand", "brown"],
    available: false,
    addedAt: "2026-02-11",
  },
  {
    id: "shoe-06",
    nameAr: "مشوار وسط البلد",
    nameEn: "Downtown Walk",
    type: "casual",
    price: "1200",
    sizes: ["39", "40", "41"],
    colors: ["white", "navy"],
    available: true,
    addedAt: "2026-02-18",
  },
  {
    id: "shoe-07",
    nameAr: "راحة يومية",
    nameEn: "Daily Comfort",
    type: "casual",
    price: "1350",
    sizes: ["40", "42", "44"],
    colors: ["black", "gray"],
    available: true,
    addedAt: "2026-03-02",
    features: ["leather"],
    suitableFor: ["everyday_wear"],
  },
  {
    id: "shoe-08",
    nameAr: "كلاسيك إسكندرية",
    nameEn: "Alex Classic",
    type: "casual",
    price: "1550",
    sizes: ["41", "42", "43"],
    colors: ["brown", "white"],
    available: true,
    addedAt: "2026-03-12",
    features: ["leather"],
    suitableFor: ["formal_events"],
  },
  {
    id: "shoe-09",
    nameAr: "ممشى النيل",
    nameEn: "Nile Walk",
    type: "casual",
    price: "1850",
    sizes: ["39", "41", "43"],
    colors: ["blue", "beige"],
    available: true,
    addedAt: "2026-03-20",
  },
  {
    id: "shoe-10",
    nameAr: "ويك إند",
    nameEn: "Weekend",
    type: "casual",
    price: "2200",
    sizes: ["40", "42", "44"],
    colors: ["green", "white"],
    available: true,
    addedAt: "2026-04-03",
  },
  {
    id: "shoe-11",
    nameAr: "هداف",
    nameEn: "Striker",
    type: "football",
    price: "1650",
    sizes: ["40", "41", "42"],
    colors: ["red", "black"],
    available: true,
    addedAt: "2026-04-14",
  },
  {
    id: "shoe-12",
    nameAr: "ملعب النجوم",
    nameEn: "Star Pitch",
    type: "football",
    price: "1950",
    sizes: ["41", "42", "43"],
    colors: ["blue", "yellow"],
    available: true,
    addedAt: "2026-05-01",
  },
  {
    id: "shoe-13",
    nameAr: "صانع اللعب",
    nameEn: "Playmaker",
    type: "football",
    price: "2300",
    sizes: ["42", "43", "44"],
    colors: ["white", "black"],
    available: true,
    addedAt: "2026-05-16",
  },
  {
    id: "shoe-14",
    nameAr: "حارس",
    nameEn: "Keeper",
    type: "football",
    price: "2600",
    sizes: ["43", "44", "45"],
    colors: ["green", "orange"],
    available: true,
    addedAt: "2026-06-01",
  },
  {
    id: "shoe-15",
    nameAr: "بطولة",
    nameEn: "Championship",
    type: "football",
    price: "3100",
    sizes: ["41", "43", "45"],
    colors: ["gold", "black"],
    available: false,
    addedAt: "2026-06-17",
  },
];

const clothingSeeds: readonly ProductSeed[] = [
  {
    id: "clothing-01",
    nameAr: "جاكيت القاهرة",
    nameEn: "Cairo Jacket",
    type: "outerwear",
    price: "1500",
    sizes: ["M", "L", "XL"],
    colors: ["black"],
    available: true,
    addedAt: "2026-01-04",
  },
  {
    id: "clothing-02",
    nameAr: "جاكيت شتوي",
    nameEn: "Winter Jacket",
    type: "outerwear",
    price: "1900",
    sizes: ["L", "XL"],
    colors: ["navy"],
    available: true,
    addedAt: "2026-01-18",
  },
  {
    id: "clothing-03",
    nameAr: "بالطو النيل",
    nameEn: "Nile Coat",
    type: "outerwear",
    price: "2600",
    sizes: ["S", "M", "L"],
    colors: ["beige"],
    available: false,
    addedAt: "2026-02-02",
  },
  {
    id: "clothing-04",
    nameAr: "قميص قطن",
    nameEn: "Cotton Shirt",
    type: "shirts",
    price: "650",
    sizes: ["S", "M", "L"],
    colors: ["white", "blue"],
    available: true,
    addedAt: "2026-02-15",
    features: [
      "cotton",
      "lightweight",
      "breathable",
      "comfortable",
      "light_color",
    ],
    suitableFor: ["hot_weather", "beach"],
    wearPosition: "upper",
  },
  {
    id: "clothing-05",
    nameAr: "قميص رسمي",
    nameEn: "Formal Shirt",
    type: "shirts",
    price: "900",
    sizes: ["M", "L", "XL"],
    colors: ["white", "gray"],
    available: true,
    addedAt: "2026-03-01",
    features: ["cotton"],
    suitableFor: ["formal_events"],
    wearPosition: "upper",
  },
  {
    id: "clothing-06",
    nameAr: "تيشيرت إسكندرية",
    nameEn: "Alex Tee",
    type: "tops",
    price: "420",
    sizes: ["S", "M", "L"],
    colors: ["blue", "white"],
    available: true,
    addedAt: "2026-03-14",
    features: ["lightweight", "light_color"],
    suitableFor: ["hot_weather", "beach"],
    wearPosition: "upper",
  },
  {
    id: "clothing-07",
    nameAr: "تيشيرت شمس",
    nameEn: "Sun Tee",
    type: "tops",
    price: "480",
    sizes: ["M", "L", "XL"],
    colors: ["yellow", "black"],
    available: false,
    addedAt: "2026-03-28",
  },
  {
    id: "clothing-08",
    nameAr: "بنطلون يومي",
    nameEn: "Everyday Trousers",
    type: "trousers",
    price: "850",
    sizes: ["30", "32", "34"],
    colors: ["black", "khaki"],
    available: true,
    addedAt: "2026-04-06",
    wearPosition: "lower",
  },
  {
    id: "clothing-09",
    nameAr: "جينز وسط البلد",
    nameEn: "Downtown Jeans",
    type: "trousers",
    price: "1100",
    sizes: ["30", "32", "36"],
    colors: ["blue"],
    available: true,
    addedAt: "2026-04-20",
    wearPosition: "lower",
  },
  {
    id: "clothing-10",
    nameAr: "فستان نسمة",
    nameEn: "Breeze Dress",
    type: "dresses",
    price: "1250",
    sizes: ["S", "M", "L"],
    colors: ["green", "pink"],
    available: true,
    addedAt: "2026-05-02",
  },
  {
    id: "clothing-11",
    nameAr: "فستان سهرة",
    nameEn: "Evening Dress",
    type: "dresses",
    price: "2200",
    sizes: ["M", "L"],
    colors: ["black", "red"],
    available: false,
    addedAt: "2026-05-17",
  },
  {
    id: "clothing-12",
    nameAr: "هودي مريح",
    nameEn: "Comfort Hoodie",
    type: "tops",
    price: "980",
    sizes: ["M", "L", "XL"],
    colors: ["gray", "navy"],
    available: true,
    addedAt: "2026-06-03",
    wearPosition: "upper",
  },
  {
    id: "clothing-13",
    nameAr: "شورت رياضي",
    nameEn: "Sport Shorts",
    type: "sportswear",
    price: "550",
    sizes: ["S", "M", "L"],
    colors: ["black", "blue"],
    available: true,
    addedAt: "2026-06-16",
  },
  {
    id: "clothing-14",
    nameAr: "تريننج النيل",
    nameEn: "Nile Tracksuit",
    type: "sportswear",
    price: "1750",
    sizes: ["M", "L", "XL"],
    colors: ["navy", "white"],
    available: true,
    addedAt: "2026-07-01",
  },
  {
    id: "clothing-15",
    nameAr: "كارديجان خفيف",
    nameEn: "Light Cardigan",
    type: "outerwear",
    price: "1350",
    sizes: ["S", "M"],
    colors: ["cream"],
    available: true,
    addedAt: "2026-07-15",
  },
];

const bagSeeds: readonly ProductSeed[] = [
  {
    id: "bag-01",
    nameAr: "شنطة النيل",
    nameEn: "Nile Bag",
    type: "tote",
    price: "900",
    sizes: ["M"],
    colors: ["blue", "black"],
    available: true,
    addedAt: "2026-08-15",
  },
  {
    id: "bag-02",
    nameAr: "حقيبة القاهرة",
    nameEn: "Cairo Backpack",
    type: "backpack",
    price: "1250",
    sizes: ["L"],
    colors: ["black"],
    available: true,
    addedAt: "2026-02-05",
  },
  {
    id: "bag-03",
    nameAr: "شنطة سفر",
    nameEn: "Travel Duffel",
    type: "travel",
    price: "1800",
    sizes: ["L"],
    colors: ["gray", "navy"],
    available: false,
    addedAt: "2026-02-20",
  },
  {
    id: "bag-04",
    nameAr: "شنطة لابتوب",
    nameEn: "Laptop Briefcase",
    type: "briefcase",
    price: "1450",
    sizes: ["M", "L"],
    colors: ["brown", "black"],
    available: true,
    addedAt: "2026-03-04",
  },
  {
    id: "bag-05",
    nameAr: "حقيبة إسكندرية",
    nameEn: "Alex Tote",
    type: "tote",
    price: "780",
    sizes: ["M"],
    colors: ["white", "blue"],
    available: true,
    addedAt: "2026-03-19",
  },
  {
    id: "bag-06",
    nameAr: "جراب صغير",
    nameEn: "Mini Pouch",
    type: "pouch",
    price: "350",
    sizes: ["S"],
    colors: ["red", "black"],
    available: true,
    addedAt: "2026-04-01",
  },
  {
    id: "bag-07",
    nameAr: "شنطة كتف",
    nameEn: "Daily Shoulder Bag",
    type: "shoulder",
    price: "690",
    sizes: ["M"],
    colors: ["beige", "brown"],
    available: true,
    addedAt: "2026-04-13",
  },
  {
    id: "bag-08",
    nameAr: "حقيبة مدرسة",
    nameEn: "School Backpack",
    type: "backpack",
    price: "820",
    sizes: ["M"],
    colors: ["green", "blue"],
    available: true,
    addedAt: "2026-04-27",
  },
  {
    id: "bag-09",
    nameAr: "شنطة رياضية",
    nameEn: "Gym Duffel",
    type: "travel",
    price: "990",
    sizes: ["L"],
    colors: ["black", "red"],
    available: true,
    addedAt: "2026-05-09",
  },
  {
    id: "bag-10",
    nameAr: "حقيبة عمل",
    nameEn: "Work Briefcase",
    type: "briefcase",
    price: "1650",
    sizes: ["L"],
    colors: ["black"],
    available: false,
    addedAt: "2026-05-22",
  },
  {
    id: "bag-11",
    nameAr: "شنطة بحر",
    nameEn: "Beach Tote",
    type: "tote",
    price: "620",
    sizes: ["L"],
    colors: ["yellow", "blue"],
    available: true,
    addedAt: "2026-06-04",
  },
  {
    id: "bag-12",
    nameAr: "حقيبة كاميرا",
    nameEn: "Camera Bag",
    type: "shoulder",
    price: "1350",
    sizes: ["M"],
    colors: ["black", "gray"],
    available: true,
    addedAt: "2026-06-18",
  },
  {
    id: "bag-13",
    nameAr: "شنطة يد كلاسيك",
    nameEn: "Classic Handbag",
    type: "handbag",
    price: "1550",
    sizes: ["M"],
    colors: ["brown", "cream"],
    available: true,
    addedAt: "2026-07-02",
  },
  {
    id: "bag-14",
    nameAr: "حقيبة خصر",
    nameEn: "Belt Bag",
    type: "pouch",
    price: "540",
    sizes: ["S"],
    colors: ["black", "green"],
    available: true,
    addedAt: "2026-07-16",
  },
  {
    id: "bag-15",
    nameAr: "شنطة سفر كبيرة",
    nameEn: "Grand Suitcase",
    type: "travel",
    price: "3200",
    sizes: ["XL"],
    colors: ["navy", "silver"],
    available: false,
    addedAt: "2026-08-01",
  },
];

const electronicsSeeds: readonly ProductSeed[] = [
  {
    id: "electronics-01",
    nameAr: "سماعة النيل",
    nameEn: "Nile Headphones",
    type: "audio",
    price: "1150",
    sizes: ["standard"],
    colors: ["black", "blue"],
    available: true,
    addedAt: "2026-08-01",
  },
  {
    id: "electronics-02",
    nameAr: "سماعة جيب",
    nameEn: "Pocket Speaker",
    type: "audio",
    price: "750",
    sizes: ["compact"],
    colors: ["red", "black"],
    available: true,
    addedAt: "2026-08-02",
  },
  {
    id: "electronics-03",
    nameAr: "شاحن سريع",
    nameEn: "Fast Charger",
    type: "power",
    price: "420",
    sizes: ["standard"],
    colors: ["white"],
    available: true,
    addedAt: "2026-08-03",
  },
  {
    id: "electronics-04",
    nameAr: "بطارية محمولة",
    nameEn: "Power Bank",
    type: "power",
    price: "890",
    sizes: ["compact"],
    colors: ["black"],
    available: false,
    addedAt: "2026-08-04",
  },
  {
    id: "electronics-05",
    nameAr: "ساعة القاهرة",
    nameEn: "Cairo Smartwatch",
    type: "wearables",
    price: "2400",
    sizes: ["40mm", "44mm"],
    colors: ["black", "silver"],
    available: true,
    addedAt: "2026-08-05",
  },
  {
    id: "electronics-06",
    nameAr: "سوار رياضي",
    nameEn: "Fitness Band",
    type: "wearables",
    price: "1300",
    sizes: ["standard"],
    colors: ["blue", "black"],
    available: true,
    addedAt: "2026-08-06",
  },
  {
    id: "electronics-07",
    nameAr: "لوحة مفاتيح",
    nameEn: "Compact Keyboard",
    type: "computer",
    price: "980",
    sizes: ["compact"],
    colors: ["white", "black"],
    available: true,
    addedAt: "2026-08-07",
  },
  {
    id: "electronics-08",
    nameAr: "ماوس لاسلكي",
    nameEn: "Wireless Mouse",
    type: "computer",
    price: "560",
    sizes: ["standard"],
    colors: ["gray", "black"],
    available: true,
    addedAt: "2026-08-08",
  },
  {
    id: "electronics-09",
    nameAr: "مصباح مكتب",
    nameEn: "Smart Desk Lamp",
    type: "home",
    price: "840",
    sizes: ["standard"],
    colors: ["white"],
    available: true,
    addedAt: "2026-08-09",
  },
  {
    id: "electronics-10",
    nameAr: "قابس ذكي",
    nameEn: "Smart Plug",
    type: "home",
    price: "390",
    sizes: ["compact"],
    colors: ["white"],
    available: false,
    addedAt: "2026-08-10",
  },
  {
    id: "electronics-11",
    nameAr: "كاميرا صغيرة",
    nameEn: "Mini Camera",
    type: "camera",
    price: "2850",
    sizes: ["compact"],
    colors: ["black"],
    available: true,
    addedAt: "2026-08-11",
  },
  {
    id: "electronics-12",
    nameAr: "حامل موبايل",
    nameEn: "Phone Stand",
    type: "accessories",
    price: "260",
    sizes: ["standard"],
    colors: ["silver", "black"],
    available: true,
    addedAt: "2026-08-12",
  },
  {
    id: "electronics-13",
    nameAr: "كابل متين",
    nameEn: "Braided Cable",
    type: "accessories",
    price: "180",
    sizes: ["1m", "2m"],
    colors: ["black", "red"],
    available: true,
    addedAt: "2026-08-13",
  },
  {
    id: "electronics-14",
    nameAr: "سماعات لاسلكية",
    nameEn: "Wireless Earbuds",
    type: "audio",
    price: "1650",
    sizes: ["compact"],
    colors: ["white", "black"],
    available: true,
    addedAt: "2026-08-14",
  },
  {
    id: "electronics-15",
    nameAr: "قارئ إلكتروني",
    nameEn: "Pocket E-reader",
    type: "computer",
    price: "3600",
    sizes: ["6-inch"],
    colors: ["black"],
    available: false,
    addedAt: "2026-08-15",
  },
];

function inCategory(
  category: Category,
  seeds: readonly ProductSeed[],
): Product[] {
  return seeds.map((seed) => ({
    ...seed,
    category,
    price: money(seed.price),
    features: seed.features ?? [],
    suitableFor: seed.suitableFor ?? [],
    wearPosition: seed.wearPosition ?? null,
  }));
}

export const products: readonly Product[] = [
  ...inCategory("shoes", shoeSeeds),
  ...inCategory("clothing", clothingSeeds),
  ...inCategory("bags", bagSeeds),
  ...inCategory("electronics", electronicsSeeds),
];

export const shoes: readonly Product[] = products.filter(
  (product) => product.category === "shoes",
);

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

export function filterProducts(constraints: ProductConstraints): Product[] {
  const query =
    constraints.query === undefined ? undefined : normalized(constraints.query);
  const matches = products.filter((product) => {
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

export function filterShoes(constraints: ShoeConstraints): Product[] {
  return filterProducts({ category: "shoes", ...constraints });
}
