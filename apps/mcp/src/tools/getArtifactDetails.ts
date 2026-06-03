import { apiGet } from "../client.js";
import { toArtifactDetails } from "../format.js";
import type { ArtifactDetails } from "../types.js";

export type GetArtifactDetailsInput = {
  artifact_id: string;
};

export async function getArtifactDetails(
  input: GetArtifactDetailsInput,
): Promise<ArtifactDetails> {
  const row = await apiGet<Record<string, unknown>>(`/artifacts/${input.artifact_id}`);
  return toArtifactDetails(row);
}
