import { notFound } from "next/navigation";
import { getProfile } from "@/lib/api";

export default async function ProfilePage({
  params,
}: {
  params: Promise<{ username: string }>;
}) {
  const { username } = await params;
  let data;
  try {
    data = await getProfile(username);
  } catch {
    notFound();
  }

  const { profile, starred_artifacts_count } = data;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">@{profile.username}</h1>
        {profile.display_name && (
          <p className="text-slate-400">{profile.display_name}</p>
        )}
        {profile.bio && <p className="mt-2 text-slate-400">{profile.bio}</p>}
        <p className="mt-2 text-sm text-slate-500">
          Credibility: <span className="text-sky-400">{profile.credibility_score}</span>
          {" · "}
          Stars given: {starred_artifacts_count}
        </p>
      </header>
    </div>
  );
}
