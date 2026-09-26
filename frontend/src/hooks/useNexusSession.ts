/**
 * useNexusSession
 */

"use client";

import * as React from "react";
import { getDevUserId, setDevUserId } from "@/services/apiClient";
import { identityService } from "@/services/identityService";
import { MeResponse, WorkspaceWithRole } from "@/services/types";

interface SessionState {
  user: MeResponse["user"] | null;
  workspace: WorkspaceWithRole | null;
  workspaces: WorkspaceWithRole[];
  isReady: boolean;
  error: string | null;
}

export function useNexusSession(): SessionState {
  const [state, setState] = React.useState<SessionState>({
    user: null,
    workspace: null,
    workspaces: [],
    isReady: false,
    error: null,
  });

  React.useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const envUserId = process.env.NEXT_PUBLIC_DEV_USER_ID;
        if (envUserId && !getDevUserId()) {
          setDevUserId(envUserId);
        }

        if (!getDevUserId()) {
          setState((prev) => ({ ...prev, isReady: true }));
          return;
        }

        const me = await identityService.getMe();
        if (cancelled) return;

        const workspace = await identityService.resolveActiveWorkspace();
        if (cancelled) return;

        setState({
          user: me.user,
          workspace,
          workspaces: me.workspaces,
          isReady: true,
          error: null,
        });
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Session bootstrap failed.";
        setState((prev) => ({
          ...prev,
          isReady: true,
          error: message,
        }));
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
