/**
 * The layering, checked rather than remembered.
 *
 * The Python side has `tests/unit/test_architecture_boundaries.py` and four
 * import-linter contracts; this is the same idea for the frontend. A layer may
 * import only layers below it, and two slices on the same layer may not import
 * each other - which is what keeps a feature deletable and stops the window
 * growing a web of shortcuts between unrelated parts of itself.
 *
 * It reads the source, so a violation fails `npm test` rather than a review.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

import { describe, expect, it } from "vitest";

/** Lowest first. A file may import its own layer's shared parts and anything below. */
const LAYERS = ["shared", "entities", "features", "widgets", "pages", "app"] as const;

const ROOT = resolve(__dirname);
const IMPORT = /from\s+"([^"]+)"/g;

function sources(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry) ? [path] : [];
  });
}

function locate(path: string): { layer: string; slice: string } | null {
  const [layer, slice] = relative(ROOT, path).split("/");
  return LAYERS.includes(layer as (typeof LAYERS)[number]) ? { layer, slice } : null;
}

function imports(file: string): string[] {
  const text = readFileSync(file, "utf8");
  return [...text.matchAll(IMPORT)]
    .map((match) => match[1])
    .filter((specifier) => specifier.startsWith("."))
    .map((specifier) => resolve(file, "..", specifier));
}

describe("Feature-Sliced Design", () => {
  const files = sources(ROOT).filter(locate);

  it("has every source file inside a layer", () => {
    const stray = sources(ROOT)
      .filter((file) => !locate(file))
      .map((file) => relative(ROOT, file))
      .filter((file) => file !== "main.tsx" && file !== "test-setup.ts");
    expect(stray).toEqual([]);
  });

  it("imports only downwards", () => {
    const wrong: string[] = [];
    for (const file of files) {
      const here = locate(file)!;
      for (const target of imports(file)) {
        const there = locate(target);
        if (!there) continue;
        if (LAYERS.indexOf(there.layer as never) > LAYERS.indexOf(here.layer as never)) {
          wrong.push(`${relative(ROOT, file)} → ${relative(ROOT, target)}`);
        }
      }
    }
    expect(wrong).toEqual([]);
  });

  it("keeps slices on one layer independent of each other", () => {
    const crossing: string[] = [];
    for (const file of files) {
      const here = locate(file)!;
      if (here.layer === "shared" || here.layer === "app") continue;
      for (const target of imports(file)) {
        const there = locate(target);
        if (!there) continue;
        if (there.layer === here.layer && there.slice !== here.slice) {
          crossing.push(`${relative(ROOT, file)} → ${relative(ROOT, target)}`);
        }
      }
    }
    expect(crossing).toEqual([]);
  });

  it("keeps the transport in shared, so one file knows how the runtime is reached", () => {
    const reaching = files
      .filter((file) => locate(file)!.layer !== "shared")
      .filter((file) => /\bfetch\(|new EventSource\(/.test(readFileSync(file, "utf8")))
      .map((file) => relative(ROOT, file));
    expect(reaching).toEqual([]);
  });

  it("never names a model, a provider or a tool implementation", () => {
    // The UI must not know which model answered or how the browser is driven.
    // A branch on either would be the core's decision, copied into TypeScript
    // and free to disagree with it.
    const forbidden = /\b(openai|anthropic|gemini|playwright|ollama|claude|gpt-4)\b/i;
    const naming = files
      .filter((file) => forbidden.test(readFileSync(file, "utf8")))
      .map((file) => relative(ROOT, file));
    expect(naming).toEqual([]);
  });
});
