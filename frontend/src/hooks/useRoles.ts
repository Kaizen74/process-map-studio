import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRole, deleteRole, listRoles, updateRole } from "../api/roles";
import type { RoleCreate, RolePatch } from "../api/types";

const rolesKey = (engagementId: string) => ["engagements", engagementId, "roles"] as const;

export function useRoles(engagementId: string) {
  return useQuery({
    queryKey: rolesKey(engagementId),
    queryFn: () => listRoles(engagementId),
    enabled: Boolean(engagementId),
  });
}

export function useCreateRole(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (role: RoleCreate) => createRole(engagementId, role),
    onSuccess: () => void client.invalidateQueries({ queryKey: rolesKey(engagementId) }),
  });
}

export function useUpdateRole(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: RolePatch }) => updateRole(id, patch),
    // Moving one lane renumbers the others, so reload the whole list.
    onSettled: () => void client.invalidateQueries({ queryKey: rolesKey(engagementId) }),
  });
}

export function useDeleteRole(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (roleId: string) => deleteRole(roleId),
    // The roles below move up a lane, so reload the whole list.
    onSuccess: () => void client.invalidateQueries({ queryKey: rolesKey(engagementId) }),
  });
}
