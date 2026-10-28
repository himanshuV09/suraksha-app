import { Card, CardContent } from "@/components/ui/card";

interface SummaryCardProps {
    title: string;
    value: number | string;
    description?: string;
}

export default function SummaryCard({
    title,
    value,
    description,
}: SummaryCardProps) {
    return (
        <Card className="h-full">
            <CardContent className="flex flex-col gap-2 p-5">
                <span className="text-sm text-muted-foreground">
                    {title}
                </span>

                <span className="text-3xl font-bold">
                    {value}
                </span>

                {description && (
                    <span className="text-xs text-muted-foreground">
                        {description}
                    </span>
                )}
            </CardContent>
        </Card>
    );
}