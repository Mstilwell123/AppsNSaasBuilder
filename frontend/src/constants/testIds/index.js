// constants/testIds/ — central registry of data-testid values used by the
// end-to-end testing agent (qabot) to locate and interact with UI elements
// during automated tests.
//
// Adding a new feature:
//   1. Create constants/testIds/<feature>.js
//   2. Export named objects (e.g. `export const SETTINGS = { ... }`)
//   3. Re-export here: `export * from './<feature>';`

export * from "./auth";
export * from "./home";
export * from "./settings";
export * from "./projects";
