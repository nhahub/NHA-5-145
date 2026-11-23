import { afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createApp as application } from "../src/app.js";
import { importCatalogue, openCatalogue } from "../src/catalogue-db.js";
import { seedProducts } from "../src/catalogue-seed.js";
const cleanups: (() => void)[] = [];
afterEach(() => {
  for (const close of cleanups.splice(0)) close();
});
export function createApp(
  options: Omit<Parameters<typeof application>[0], "repository"> = {},
) {
  const directory = mkdtempSync(join(tmpdir(), "copilot-test-db-"));
  const file = join(directory, "catalogue.sqlite");
  importCatalogue(file, seedProducts);
  const repository = openCatalogue(file);
  cleanups.push(() => {
    repository.close();
    rmSync(directory, { recursive: true, force: true });
  });
  return application({ ...options, repository });
}
