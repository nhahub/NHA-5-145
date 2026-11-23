import { readFileSync, writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import { importCatalogue, openCatalogue } from "../src/catalogue-db.js";
import { parseSearch, searchProducts } from "../src/catalogue-query.js";
import {
  installSemanticIndex,
  semanticRanker,
  type SemanticIndex,
  type QueryEmbedding,
} from "../src/catalogue-semantic.js";
import type { Product } from "../src/catalogue.js";

const [database, inputFile, outputFile] = process.argv.slice(2);
const input = JSON.parse(readFileSync(inputFile, "utf8")) as {
  products?: Product[];
  index?: SemanticIndex;
  queries: { id: string; query: unknown; embedding?: QueryEmbedding }[];
};
if (input.products) importCatalogue(database, input.products);
const repo = openCatalogue(database);
try {
  if (input.index) installSemanticIndex(repo, input.index);
  const results = input.queries.map((row) => {
    const query = parseSearch(row.query);
    const start = performance.now();
    const lexical = searchProducts(repo, query, "offline-only");
    const lexicalMs = performance.now() - start;
    const next = performance.now();
    const hybrid = row.embedding
      ? searchProducts(
          repo,
          query,
          "offline-only",
          semanticRanker(repo, row.embedding),
        )
      : null;
    return {
      id: row.id,
      lexical,
      hybrid,
      lexical_ms: lexicalMs,
      hybrid_ms: performance.now() - next,
    };
  });
  writeFileSync(
    outputFile,
    JSON.stringify({ results, rss_bytes: process.memoryUsage().rss }, null, 2) +
      "\n",
  );
} finally {
  repo.close();
}
