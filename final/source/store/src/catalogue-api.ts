import { semanticRanker } from "./catalogue-semantic.js";
import { Router } from "express";
import { equalSecret } from "./shopper-http.js";
import type { ProductRepository } from "./product-repository.js";
import {
  CatalogueError,
  digest,
  parseSearch,
  parseDetails,
  searchProducts,
  productDetails,
} from "./catalogue-query.js";

export function catalogueRoutes(
  repository: ProductRepository,
  secret: string,
  ranking: "lexical" | "hybrid" = "lexical",
) {
  const router = Router();
  router.use((request, response, next) => {
    response.set("Cache-Control", "no-store");
    if (!equalSecret(request.headers["x-service-secret"], secret)) {
      response.sendStatus(403);
      return;
    }
    next();
  });
  for (const kind of ["search", "details"] as const)
    router.post("/" + kind, (request, response) => {
      try {
        const body = request.body;
        const hybrid = kind === "search" && ranking === "hybrid";
        const { query_embedding, ...searchBody } =
          hybrid && body && typeof body === "object" ? body : {};
        // Validate freshness even for conditional reads: a stale index is not a cache hit.
        const ranker = hybrid
          ? semanticRanker(repository, query_embedding)
          : undefined;
        const query =
          kind === "search"
            ? parseSearch(hybrid ? searchBody : body)
            : parseDetails(request.body);
        const etag =
          '"' +
          digest([
            kind,
            query,
            ranking,
            hybrid ? query_embedding : null,
            repository.revision(),
          ]) +
          '"';
        response.set("ETag", etag);
        if (request.headers["if-none-match"] === etag) {
          response.status(304).end();
          return;
        }
        const result =
          "ids" in query
            ? productDetails(repository, query)
            : searchProducts(repository, query, secret, ranker);
        response.json(result);
      } catch (error) {
        const code =
          error instanceof CatalogueError ? error.code : "unavailable";
        response
          .status(
            code === "invalid_query"
              ? 400
              : code === "stale_cursor" || code === "stale_index"
                ? 409
                : code === "record_too_large"
                  ? 413
                  : 503,
          )
          .json({ code });
      }
    });
  return router;
}
