import type { TemplateSummary } from "../lib/templates";
import { request } from "./request";

export const listTemplatePlans = () => request<TemplateSummary[]>("/templates/interview/plans");
