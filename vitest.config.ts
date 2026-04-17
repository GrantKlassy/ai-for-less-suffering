import "vitest/config";
import { getViteConfig } from "astro/config";

// getViteConfig spins up the Astro environment so virtual modules like
// `astro:content` resolve during tests. Without it, any file that imports
// from astro:content fails to load even if the test only exercises pure
// helpers in the same module. The triple-slash reference above augments
// Vite's UserConfig with vitest's `test` property.
export default getViteConfig({
  test: {
    include: ["src/**/*.test.ts"],
  },
});
