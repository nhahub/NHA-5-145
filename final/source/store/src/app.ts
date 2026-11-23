import type { ProductRepository } from "./product-repository.js";
import { catalogueRoutes } from "./catalogue-api.js";
import express, {
  type Express,
  type NextFunction,
  type Request,
  type Response,
} from "express";
import {
  LinkTickets,
  privateShopperRoutes,
  browserLinkRoutes,
} from "./shopper-link.js";
import {
  MemoryShopperStateStore,
  type ShopperStateStore,
} from "./shopper-state-store.js";
import {
  ShopperRegistry,
  credentialDigest,
  type ShopperState,
} from "./shopper-state.js";
import { shopperHttp, shopper } from "./shopper-http.js";
import { validatePublicOrigin } from "../../bridge/src/public-origins.js";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { type CartLine } from "./guarded-cart.js";
import {
  StoreEventLog,
  streamSink,
  type CartChange,
  type Outcome,
} from "./event-log.js";

import {
  categories,
  money,
  type Category,
  type Money,
  type ProductConstraints,
  type ProductSort,
} from "./catalogue.js";
import {
  renderAccount,
  renderCart,
  renderCartContents,
  renderCategory,
  renderCheckout,
  renderHome,
  renderLogin,
  renderOrders,
  renderOrderComplete,
  renderProduct,
} from "./views.js";

const orderHistoryPath = "/account/orders";
const loginPath = `/login?next=${encodeURIComponent(orderHistoryPath)}`;

function requestedNextPath(value: unknown): string {
  const requestedPath = firstQueryValue(value);
  return requestedPath === orderHistoryPath ? requestedPath : orderHistoryPath;
}

function firstQueryValue(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function nonEmptyQueryValue(value: unknown): string | undefined {
  const text = firstQueryValue(value)?.trim();
  return text === undefined || text === "" ? undefined : text;
}

function priceFromQuery(value: unknown): Money | undefined {
  const text = nonEmptyQueryValue(value);
  if (text === undefined) return undefined;
  try {
    return money(text);
  } catch {
    return undefined;
  }
}

function categoryFromValue(value: unknown): Category | undefined {
  return categories.find((category) => category === value);
}

function availabilityFromQuery(value: unknown): boolean | undefined {
  if (value === "available") return true;
  if (value === "unavailable") return false;
  return undefined;
}

function sortFromQuery(value: unknown): ProductSort | undefined {
  return value === "cheapest" || value === "newest" ? value : undefined;
}

function constraintsFromQuery(
  category: Category,
  query: Record<string, unknown>,
): ProductConstraints {
  return {
    category,
    query: nonEmptyQueryValue(query.q),
    type: nonEmptyQueryValue(query.type),
    minPrice: priceFromQuery(query.min_price),
    maxPrice: priceFromQuery(query.max_price),
    size: nonEmptyQueryValue(query.size),
    color: nonEmptyQueryValue(query.color),
    availability: availabilityFromQuery(query.availability),
    sort: sortFromQuery(query.sort),
  };
}

function stateFilters(constraints: ProductConstraints) {
  return {
    q: constraints.query ?? null,
    type: constraints.type ?? null,
    min_price: constraints.minPrice ?? null,
    max_price: constraints.maxPrice ?? null,
    size: constraints.size ?? null,
    color: constraints.color ?? null,
    availability:
      constraints.availability === undefined
        ? null
        : constraints.availability
          ? "available"
          : "unavailable",
    sort: constraints.sort ?? null,
  };
}

export function createApp(options: {
  repository: ProductRepository;
  catalogueRanking?: "lexical" | "hybrid";
  serviceSecret?: string;
  panelOrigin?: string;
  clock?: () => number;
  evaluation?: boolean;
  origin?: string;
  capacity?: number;
  ttlMs?: number;
  events?: StoreEventLog;
  /** Where Shopper state is kept; defaults to in-memory (no restart survival). */
  stateStore?: ShopperStateStore;
}): Express {
  const repository = options.repository;
  const events = options.events ?? new StoreEventLog(streamSink());
  const app = express();
  // Cart-change records are held until the save decision, so the log states what the
  // Shopper actually received (a failed save is logged as rejected with that status).
  function logChange(
    response: Response,
    change: CartChange,
    outcome: Outcome,
    status: number,
  ): void {
    const held = response.locals.heldChanges as
      | Array<[CartChange, Outcome, number]>
      | undefined;
    if (held) held.push([change, outcome, status]);
    else events.cartChange(change, outcome, status);
  }
  const registry = new ShopperRegistry({
    ...options,
    store:
      options.stateStore ??
      new MemoryShopperStateStore({ clock: options.clock }),
  });
  const sourceDirectory = dirname(fileURLToPath(import.meta.url));
  app.use(express.urlencoded({ extended: false }));
  app.use(express.json());
  // Catalogue/commerce handlers below are synchronous. Hold one read snapshot from
  // validation through response/order serialization so an offline import cannot
  // interleave a different price or variant between those steps.
  app.use((_request, _response, next) => repository.snapshot(next));
  app.use(
    "/__internal/catalogue",
    catalogueRoutes(
      repository,
      options.serviceSecret ?? "",
      options.catalogueRanking,
    ),
  );
  app.use("/assets", express.static(resolve(sourceDirectory, "../public")));
  app.use(
    "/bridge",
    express.static(resolve(sourceDirectory, "../../bridge/dist")),
  );

  const production = process.env.COPILOT_ENV === "production";
  const audience = validatePublicOrigin(
    options.panelOrigin ?? "http://localhost:4100",
    production,
  );
  const origin = validatePublicOrigin(
    options.origin ?? "http://localhost:4000",
    production,
  );
  if (audience === origin)
    throw new Error("Panel and Storefront origins must differ");
  const tickets = new LinkTickets(options.clock);
  app.use(
    "/__internal",
    privateShopperRoutes(
      registry,
      tickets,
      options.serviceSecret ?? "",
      audience,
    ),
  );
  app.use(
    shopperHttp(registry, {
      origin,
      panelOrigin: audience,
      secure: origin.startsWith("https:"),
      evaluation: !production && options.evaluation === true,
      snapshot: (read) => repository.snapshot(read),
      record: (change, outcome, status) =>
        events.cartChange(change, outcome, status),
    }),
  );
  app.use("/__copilot", browserLinkRoutes(tickets, audience));
  app.get("/__shopper", (_request, response) => {
    response.json({ csrf: shopper(response).csrf });
  });

  app.get("/", (_request, response) => {
    response.type("html").send(renderHome());
  });

  app.get("/cart", (_request, response) => {
    const cart = shopper(response).cart;
    response
      .type("html")
      .send(renderCart(repository, cart.lines, cart.revision));
  });

  app.post("/cart/clear", (request, response) => {
    const cart = shopper(response).cart;
    if (
      !cart.consume(
        request.body?.copilot_confirmation,
        "clear_cart",
        request.body?.cart_revision,
      )
    ) {
      response
        .status(403)
        .type("html")
        .send(
          renderCart(
            repository,
            cart.lines,
            cart.revision,
            "انتهى التأكيد أو تغيرت السلة. لم يتم الإفراغ.",
          ),
        );
      logChange(response, "clear", "unconfirmed", response.statusCode);
      return;
    }
    cart.clear();
    response.redirect(303, "/cart");
    logChange(response, "clear", "ok", response.statusCode);
  });

  app.post("/cart/items", (request, response) => {
    const cart = shopper(response).cart;
    const productId = request.body?.product_id;
    const product =
      typeof productId === "string" ? repository.get(productId) : undefined;
    if (product === undefined) {
      response.status(404).json({ error: "unknown_product" });
      logChange(response, "add", "unknown_product", response.statusCode);
      return;
    }
    if (!product.available) {
      response.status(409).json({ error: "product_unavailable" });
      logChange(response, "add", "unavailable", response.statusCode);
      return;
    }
    if (!cart.edit("add", request.body ?? {})) {
      response.status(409).json({ error: "invalid_or_stale_cart_edit" });
      logChange(response, "add", "rejected", response.statusCode);
      return;
    }
    response.json(cartView(shopper(response)));
    logChange(response, "add", "ok", response.statusCode);
  });

  function cartView(state: ShopperState) {
    const { cart, binding } = state;
    return {
      shopper_context: credentialDigest(
        binding.shopper_id + ":" + binding.generation,
      ),
      ...cart.state,
      undo: cart.undo,
      count: cart.lines.reduce((sum, line) => sum + line.quantity, 0),
      html: renderCartContents(repository, cart.lines, cart.revision),
    };
  }
  app.get("/cart/state", (_request, response) => {
    response.set("Cache-Control", "no-store").json(cartView(shopper(response)));
  });
  for (const kind of ["quantity", "remove", "undo"] as const) {
    app.post(`/cart/${kind}`, (request, response) => {
      const cart = shopper(response).cart;
      if (!cart.edit(kind, request.body ?? {})) {
        response.status(409).json({ error: "invalid_or_stale_cart_edit" });
        logChange(response, kind, "rejected", response.statusCode);
        return;
      }
      response.json(cartView(shopper(response)));
      logChange(response, kind, "ok", response.statusCode);
    });
  }

  app.get("/checkout", (_request, response) => {
    const cart = shopper(response).cart;
    response
      .type("html")
      .send(renderCheckout(repository, cart.lines, cart.revision));
  });

  app.post("/checkout/submit", (request, response) => {
    const cart = shopper(response).cart;
    if (
      !cart.consume(
        request.body?.copilot_confirmation,
        "submit_checkout",
        request.body?.cart_revision,
      )
    ) {
      response
        .status(403)
        .type("html")
        .send(
          renderCheckout(
            repository,
            cart.lines,
            cart.revision,
            "انتهى التأكيد أو تغيرت السلة. لم يتم تسجيل طلب.",
          ),
        );
      logChange(response, "checkout", "unconfirmed", response.statusCode);
      return;
    }
    if (
      request.body?.card_number !== "0000 0000 0000 0000" ||
      request.body?.card_expiry !== "01/30" ||
      request.body?.card_security_code !== "000"
    ) {
      response
        .status(400)
        .type("html")
        .send(
          renderCheckout(
            repository,
            cart.lines,
            cart.revision,
            "استخدم بيانات الدفع الخيالية المعروضة فقط. لم يتم تسجيل طلب.",
          ),
        );
      logChange(response, "checkout", "invalid_payment", response.statusCode);
      return;
    }
    response.redirect(303, `/order/complete/${cart.submitOrder()}`);
    logChange(response, "checkout", "ok", response.statusCode);
  });

  app.get("/order/complete/:orderId", (request, response) => {
    const cart = shopper(response).cart;
    if (
      !cart.state.orders.some((order) => order.id === request.params.orderId)
    ) {
      response.status(404).type("text").send("Unknown fictional order");
      return;
    }
    response.type("html").send(renderOrderComplete(request.params.orderId));
  });

  app.get("/account", (_request, response) => {
    response.type("html").send(renderAccount());
  });

  app.get("/login", (request, response) => {
    response
      .type("html")
      .send(renderLogin(requestedNextPath(request.query.next)));
  });

  app.post("/login", (request, response) => {
    const body = request.body ?? {};
    const username = body.username;
    const password = body.password;
    if (
      typeof username !== "string" ||
      username.trim() === "" ||
      typeof password !== "string" ||
      password === ""
    ) {
      response.status(400).type("html").send(renderLogin(orderHistoryPath));
      return;
    }

    shopper(response).loggedIn = true;
    response.redirect(303, requestedNextPath(body.next));
  });

  app.get(orderHistoryPath, (request, response) => {
    const cart = shopper(response).cart;
    if (!shopper(response).loggedIn) {
      response.redirect(302, loginPath);
      return;
    }
    response.type("html").send(renderOrders(cart.state.orders));
  });

  app.get("/__catalogue/v1/products", (_request, response) => {
    response.set("Cache-Control", "no-store").json({
      v: 1,
      currency: "EGP",
      products: repository.all().map((product) => ({
        id: product.id,
        category: product.category,
        name_ar: product.nameAr,
        name_en: product.nameEn,
        product_type: product.type,
        price: product.price,
        sizes: product.sizes,
        colors: product.colors,
        available: product.available,
        added_at: product.addedAt,
        features: product.features,
        suitable_for: product.suitableFor,
        wear_position: product.wearPosition,
      })),
    });
  });

  app.get("/p/:productId", (request, response) => {
    const product = repository.get(request.params.productId);
    if (product === undefined) {
      response.status(404).type("text").send("Unknown product");
      return;
    }
    response.type("html").send(renderProduct(product));
  });

  app.get("/c/:category", (request, response) => {
    const category = categoryFromValue(request.params.category);
    if (category === undefined) {
      response.status(404).type("text").send("Unknown category");
      return;
    }
    const constraints = constraintsFromQuery(category, request.query);
    response
      .type("html")
      .send(renderCategory(repository.filter(constraints), constraints));
  });

  app.post("/__test/reset", (_request, response) => {
    const cart = shopper(response).cart;
    cart.reset();
    response.status(204).send();
  });

  app.post("/__test/cart", (request, response) => {
    const cart = shopper(response).cart;
    if (!cart.seed(request.body?.lines as CartLine[])) {
      response.status(400).json({ error: "invalid_cart_seed" });
      return;
    }
    response.status(204).send();
  });

  app.get("/__test/cart-state", (_request, response) => {
    const cart = shopper(response).cart;
    response.set("Cache-Control", "no-store").json(cart.state);
  });

  app.get("/__test/state", (request, response) => {
    const requestedCategory =
      firstQueryValue(request.query.category) ?? "shoes";
    const category = categoryFromValue(requestedCategory);
    if (category === undefined) {
      response.status(400).json({ error: "unknown category" });
      return;
    }
    const constraints = constraintsFromQuery(category, request.query);
    const matchingProducts = repository.filter(constraints);
    const legacyShoeState = request.query.category === undefined;
    response.json({
      ...(legacyShoeState ? {} : { category }),
      filters: legacyShoeState
        ? {
            type: constraints.type ?? null,
            min_price: constraints.minPrice ?? null,
            max_price: constraints.maxPrice ?? null,
          }
        : stateFilters(constraints),
      product_ids: matchingProducts.map((product) => product.id),
      product_count: matchingProducts.length,
    });
  });

  app.use(
    (
      error: unknown,
      request: Request,
      _response: Response,
      next: NextFunction,
    ) => {
      // Express marks a shopper's malformed request (bad JSON, oversized body) with a
      // 4xx status; only server errors are worth an error record.
      const status = (error as { status?: unknown } | null)?.status;
      if (!(typeof status === "number" && status < 500)) {
        const route: unknown = request.route?.path;
        events.error(error, route);
      }
      next(error);
    },
  );

  return app;
}
