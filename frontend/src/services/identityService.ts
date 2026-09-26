/**
 * NEXUS Identity Service
 * Wraps GET /me and workspace helpers.
 */

import { api, getActiveWorkspaceId, setActiveWorkspaceId } from "./apiClient";
import { MeResponse, WorkspaceWithRole } from "./types";

export const identityService = {
  async getMe(): Promise<MeResponse> {
    return api.get<MeResponse>("/me");
  },

  async resolveActiveWorkspace(): Promise<WorkspaceWithRole | null> {
    const me = await this.getMe();
    if (!me.workspaces.length) return null;

    const stored = getActiveWorkspaceId();
    const match = stored ? me.workspaces.find((w) => w.id === stored) : null;
    const workspace = match ?? me.workspaces[0];

    setActiveWorkspaceId(workspace.id);
    return workspace;
  },

  selectWorkspace(workspaceId: string): void {
    setActiveWorkspaceId(workspaceId);
  },
};
