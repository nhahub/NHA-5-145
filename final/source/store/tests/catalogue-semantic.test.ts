import { expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import request from "supertest";
import { importCatalogue, openCatalogue } from "../src/catalogue-db.js";
import { seedProducts } from "../src/catalogue-seed.js";
import { createApp } from "../src/app.js";
import {
  EMBEDDING_MODEL,
  EMBEDDING_REVISION,
  installSemanticIndex,
} from "../src/catalogue-semantic.js";
it("serves hybrid evidence only with a current index and valid private query vector", async () => {
  const directory = mkdtempSync(join(tmpdir(), "copilot-vector-test-"));
  const file = join(directory, "catalogue.sqlite");
  importCatalogue(file, seedProducts);
  const repository = openCatalogue(file);
  const vector = Array.from({ length: 384 }, (_, i) => (i === 0 ? 1 : 0));
  const index = {
    model: EMBEDDING_MODEL,
    model_revision: EMBEDDING_REVISION,
    catalogue_revision: repository.revision(),
    vectors: Object.fromEntries(seedProducts.map((p) => [p.id, vector])),
  };
  const secret = "test-semantic-service-secret-only";
  try {
    installSemanticIndex(repository, index);
    const app = createApp({
      repository,
      serviceSecret: secret,
      catalogueRanking: "hybrid",
    });
    const body = {
      v: 1,
      query: "Cairo",
      predicates: [],
      requirements: [],
      unverified_requirements: [],
      sort: "relevance",
      cursor: null,
      query_embedding: {
        model: EMBEDDING_MODEL,
        model_revision: EMBEDDING_REVISION,
        vector,
      },
    };
    const first = await request(app)
      .post("/__internal/catalogue/search")
      .set("x-service-secret", secret)
      .send(body);
    expect(first.status).toBe(200);
    expect(first.body.ranking).toBe("hybrid");
    const invalid = await request(app)
      .post("/__internal/catalogue/search")
      .set("x-service-secret", secret)
      .send({
        ...body,
        query_embedding: { ...body.query_embedding, vector: [1] },
      });
    expect(invalid.status).toBe(400);
    importCatalogue(
      file,
      seedProducts.map((p) =>
        p.id === "shoe-01" ? { ...p, available: false } : p,
      ),
    );
    expect(
      (
        await request(app)
          .post("/__internal/catalogue/search")
          .set("x-service-secret", secret)
          .send(body)
      ).body.code,
    ).toBe("stale_index");
  } finally {
    repository.close();
    rmSync(directory, { recursive: true, force: true });
  }
});
