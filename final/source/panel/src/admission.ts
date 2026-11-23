/** Access codes stay in this form and its POST body, never URLs or browser storage. */
export async function requireAdmission(
  root: HTMLElement,
  agent: string,
  csrf: string,
  reloadAfter = false,
): Promise<void> {
  const status = await fetch(`${agent}/shopper/admission`, {
    credentials: "include",
  });
  if (!status.ok) throw new Error("Demo access status unavailable");
  const payload = (await status.json()) as {
    required: boolean;
    admitted: boolean;
  };
  if (!payload.required || payload.admitted) return;
  const existing = root.querySelector(".admission-entry");
  if (existing) return;
  const section = document.createElement("section");
  section.className = "admission-entry";
  section.innerHTML = `
    <h2>جرّب مساعد التسوّق</h2>
    <p>أدخل رمز الدخول لتفعيل المساعد. يمكنك تصفّح المتجر بدون رمز.</p>
    <form>
      <label for="admission-code">رمز الدخول / Access code</label>
      <input id="admission-code" type="password" autocomplete="off" maxlength="128" required />
      <button type="submit">تفعيل المساعد / Activate</button>
      <p role="status" aria-live="polite"></p>
    </form>`;
  root.prepend(section);
  const input = section.querySelector<HTMLInputElement>("input")!;
  const button = section.querySelector<HTMLButtonElement>("button")!;
  const feedback = section.querySelector<HTMLElement>('[role="status"]')!;
  input.focus();
  await new Promise<void>((resolve) => {
    section.querySelector("form")!.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (button.disabled) return;
      button.disabled = true;
      feedback.textContent = "جارٍ التحقق… / Checking…";
      let code = input.value;
      input.value = "";
      try {
        const response = await fetch(`${agent}/shopper/admission`, {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json", "x-csrf-token": csrf },
          body: JSON.stringify({ code }),
        });
        code = "";
        if (!response.ok) {
          feedback.textContent =
            response.status === 429
              ? "الخدمة مشغولة. انتظر قليلًا ثم حاول بنفسك. / Busy. Please wait and retry."
              : "الرمز غير صالح، انتهى أو استُخدم بالكامل. اطلب رمزًا صالحًا. / Code unavailable or expired.";
          return;
        }
        section.remove();
        resolve();
        if (reloadAfter) window.location.reload();
      } catch {
        feedback.textContent =
          "تعذر الاتصال. حاول ثانية. / Connection failed. Try again.";
      } finally {
        code = "";
        button.disabled = false;
      }
    });
  });
}
