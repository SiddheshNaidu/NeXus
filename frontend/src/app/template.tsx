import { NexusPreloader } from "@/components/ui/nexus-preloader";

export default function Template({ children }: { children: React.ReactNode }) {
  return <NexusPreloader>{children}</NexusPreloader>;
}


