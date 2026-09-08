/**
 * What to put on screen when something failed.
 *
 * It says what actually happened wherever there is anything to say. The version
 * that returned one friendly sentence for everything cost an afternoon: a
 * window that reports "the runtime is not answering" for a transport error, a
 * permission error and a genuinely absent runtime alike is a window nobody can
 * diagnose without standing in front of it.
 */
export function describe(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string" && error) return error;
  if (error && typeof error === "object") {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message) return message;
    const text = String(error);
    if (text && text !== "[object Object]") return text;
  }
  return "The local runtime is not answering.";
}
