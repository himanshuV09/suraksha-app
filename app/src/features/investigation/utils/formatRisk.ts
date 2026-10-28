export function formatRisk(score: number): string {

    if (score >= 80) return "High";

    if (score >= 50) return "Medium";

    return "Low";

}