import type { Application } from "express";

export async function loadWidget(): Promise<unknown> {
  return import("@scope/widget/runtime");
}

export function identity(app: Application): Application {
  return app;
}
