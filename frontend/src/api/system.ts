import { request } from "./request";
import type { Health } from "./types";

export const getHealth = () => request<Health>("/health");
