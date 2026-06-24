const API_BASE = "";

export async function analyzeRepository(repositoryUrl) {
  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repository_url: repositoryUrl }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Analysis failed");
  }
  return data;
}
