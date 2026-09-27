/**
 * useNexusSession
 */

"use client";

import * as React from "react";
import { getDevUserId, setDevUserId, clearDevUserId } from "@/services/apiClient";
import { identityService } from "@/services/identityService";
import { MeResponse, WorkspaceWithRole } from "@/services/types";

interface SessionState {
  user: MeResponse["user"] | null;
  workspace: WorkspaceWithRole | null;
  workspaces: WorkspaceWithRole[];
  isReady: boolean;
  error: string | null;
  /** Call with a valid UUID to sign in and bootstrap the session. */
  login: (userId: string) => Promise<void>;
  /** Clear credentials and reset session state. */
  logout: () => void;
}

export function useNexusSession(): SessionState {
  const [trigger, setTrigger] = React.useState(0);
  const [state, setState] = React.useState<Omit<SessionState, "login" | "logout">>({
    user: null,
    workspace: null,
    workspaces: [],
    isReady: false,
    error: null,
  });

  React.useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setState((prev) => ({ ...prev, isReady: false, error: null }));

      try {
        const envUserId = process.env.NEXT_PUBLIC_DEV_USER_ID;
        if (envUserId && !getDevUserId()) {
          setDevUserId(envUserId);
        }

        if (!getDevUserId()) {
          setState({ user: null, workspace: null, workspaces: [], isReady: true, error: null });
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
        setState({ user: null, workspace: null, workspaces: [], isReady: true, error: message });
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [trigger]);

  const login = React.useCallback(async (userId: string) => {
    setDevUserId(userId);
    setTrigger((t) => t + 1);
  }, []);

  const logout = React.useCallback(() => {
    clearDevUserId();
    setState({ user: null, workspace: null, workspaces: [], isReady: true, error: null });
  }, []);

  return { ...state, login, logout };
}
