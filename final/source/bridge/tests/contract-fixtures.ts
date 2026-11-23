import { readFileSync } from "node:fs";

const fixtures = new URL("../../protocol/v1/fixtures/", import.meta.url);

export function loadFixture(path: string): unknown {
  return JSON.parse(readFileSync(new URL(path, fixtures), "utf8"));
}
