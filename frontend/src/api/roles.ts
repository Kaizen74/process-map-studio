import { request } from "./request";
import type { Role, RoleCreate, RolePatch } from "./types";

export const listRoles = (engagementId: string) =>
  request<Role[]>(`/engagements/${encodeURIComponent(engagementId)}/roles`);

export const createRole = (engagementId: string, role: RoleCreate) =>
  request<Role>(`/engagements/${encodeURIComponent(engagementId)}/roles`, { method: "POST", body: role });

export const updateRole = (roleId: string, patch: RolePatch) =>
  request<Role>(`/roles/${encodeURIComponent(roleId)}`, { method: "PATCH", body: patch });

/** DELETE /roles/{rid} (DECISIONS 93): only a role nothing uses; otherwise a 409 says why. */
export const deleteRole = (roleId: string) =>
  request<null>(`/roles/${encodeURIComponent(roleId)}`, { method: "DELETE" });
