/** Non-authorizing document marker; never part of semantic Snapshot data. */
export function shopperContext(document: Document): string {
  if (document.documentElement.hasAttribute("data-shopper-invalid")) return "";
  return (
    document.querySelector<HTMLMetaElement>('meta[name="copilot-context"]')
      ?.content ?? ""
  );
}

export function matchesShopperContext(
  document: Document,
  expected: unknown,
): boolean {
  const current = shopperContext(document);
  return (
    !document.documentElement.hasAttribute("data-shopper-invalid") &&
    /^[a-f0-9]{64}$/.test(current) &&
    current === expected
  );
}
