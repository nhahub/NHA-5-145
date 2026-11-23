import { installSemanticIndex } from "../src/catalogue-semantic.js";
import { resolve } from "node:path";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import {
  exportCatalogue,
  importCatalogue,
  openCatalogue,
} from "../src/catalogue-db.js";
import { seedProducts } from "../src/catalogue-seed.js";

const args = process.argv.slice(2);
const option = (name: string) => {
  const index = args.indexOf(name);
  if (index < 0) return undefined;
  if (!args[index + 1] || args[index + 1].startsWith("--"))
    throw new Error(`Missing ${name} argument`);
  return args[index + 1];
};
const file = resolve(option("--database") ?? "../work/catalogue.sqlite");
const output = option("--export");
const index = option("--index");
if (index) {
  const repo = openCatalogue(file);
  try {
    installSemanticIndex(
      repo,
      JSON.parse(readFileSync(resolve(index), "utf8")),
    );
  } finally {
    repo.close();
  }
} else if (output) {
  writeFileSync(
    resolve(output),
    JSON.stringify(exportCatalogue(file), null, 2) + "\n",
  );
} else {
  mkdirSync(resolve(file, ".."), { recursive: true });
  importCatalogue(file, seedProducts);
  console.log("Catalogue seed import complete.");
}
