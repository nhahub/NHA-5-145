import type { ProductRepository } from "./product-repository.js";
import { CatalogueError } from "./catalogue-query.js";

export const EMBEDDING_MODEL =
  "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2";
export const EMBEDDING_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42";
export interface QueryEmbedding {
  model: string;
  model_revision: string;
  vector: number[];
}
export interface SemanticIndex {
  model: string;
  model_revision: string;
  catalogue_revision: number;
  vectors: Record<string, number[]>;
}
function validVector(value: unknown): value is number[] {
  return (
    Array.isArray(value) &&
    value.length === 384 &&
    value.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    Math.abs(value.reduce((sum, v) => sum + v * v, 0) - 1) < 0.01
  );
}
function modelMatches(value: { model: string; model_revision: string }) {
  return (
    value.model === EMBEDDING_MODEL &&
    value.model_revision === EMBEDDING_REVISION
  );
}
export function installSemanticIndex(
  repo: ProductRepository,
  index: SemanticIndex,
): void {
  if (
    !modelMatches(index) ||
    index.catalogue_revision !== repo.revision() ||
    Object.keys(index.vectors).length !== repo.all().length ||
    repo.all().some((p) => !validVector(index.vectors[p.id]))
  )
    throw new CatalogueError("stale_index");
  const db = repo.database;
  db.exec("BEGIN IMMEDIATE");
  try {
    db.exec(
      "CREATE TABLE IF NOT EXISTS catalogue_vectors(id TEXT PRIMARY KEY, vector TEXT NOT NULL); CREATE TABLE IF NOT EXISTS catalogue_vector_meta(id INTEGER PRIMARY KEY, document TEXT NOT NULL); DELETE FROM catalogue_vectors; DELETE FROM catalogue_vector_meta;",
    );
    const statement = db.prepare("INSERT INTO catalogue_vectors VALUES(?,?)");
    for (const [id, vector] of Object.entries(index.vectors))
      statement.run(id, JSON.stringify(vector));
    db.prepare("INSERT INTO catalogue_vector_meta VALUES(1,?)").run(
      JSON.stringify({
        model: index.model,
        model_revision: index.model_revision,
        catalogue_revision: index.catalogue_revision,
      }),
    );
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}
export function semanticRanker(repo: ProductRepository, input: unknown) {
  if (!input || typeof input !== "object")
    throw new CatalogueError("invalid_query");
  const embedding = input as QueryEmbedding;
  if (
    !modelMatches(embedding) ||
    !validVector(embedding.vector) ||
    Object.keys(embedding).some(
      (k) => !["model", "model_revision", "vector"].includes(k),
    )
  )
    throw new CatalogueError("invalid_query");
  try {
    const row = repo.database
      .prepare("SELECT document FROM catalogue_vector_meta WHERE id=1")
      .get();
    const meta = JSON.parse(String(row?.document));
    if (!modelMatches(meta) || meta.catalogue_revision !== repo.revision())
      throw new Error();
  } catch {
    throw new CatalogueError("stale_index");
  }
  return (_query: string, eligible: string[], lexical: string[]): string[] => {
    const vectors = repo.database
      .prepare("SELECT id,vector FROM catalogue_vectors")
      .all();
    const allowed = new Set(eligible);
    const semantic = vectors
      .filter((row) => allowed.has(String(row.id)))
      .map((row) => {
        const vector: number[] = JSON.parse(String(row.vector));
        if (!validVector(vector)) throw new CatalogueError("stale_index");
        return {
          id: String(row.id),
          score: vector.reduce((sum, v, i) => sum + v * embedding.vector[i], 0),
        };
      })
      .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id))
      .map((row) => row.id);
    const scores = new Map<string, number>();
    for (const list of [lexical, semantic])
      list.forEach((id, i) =>
        scores.set(id, (scores.get(id) ?? 0) + 1 / (61 + i)),
      );
    return [...scores.keys()].sort(
      (a, b) => scores.get(b)! - scores.get(a)! || a.localeCompare(b),
    );
  };
}
