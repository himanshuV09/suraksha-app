// components/common/EmptyState.tsx

interface EmptyStateProps {
    message: string;
}

export default function EmptyState({
    message,
}: EmptyStateProps) {
    return (
        <div className="flex h-full items-center justify-center text-sm text-slate-500">
            {message}
        </div>
    );
}