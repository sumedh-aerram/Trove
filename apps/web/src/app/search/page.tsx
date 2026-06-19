import { LandscapeView } from "@/components/LandscapeView";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  return <LandscapeView initialQuery={sp.q || ""} />;
}
