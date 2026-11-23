/** Public configuration only; service destinations and secrets never belong here. */
export function validatePublicOrigin(raw: string, production: boolean): string {
  const url = new URL(raw);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (
    url.origin !== raw ||
    url.username ||
    url.password ||
    url.hostname.includes("*") ||
    /[\s\\"<>]/u.test(raw) ||
    !["http:", "https:"].includes(url.protocol) ||
    (url.protocol === "http:" && (production || !local))
  )
    throw new Error("Invalid configured public origin");
  return raw;
}
