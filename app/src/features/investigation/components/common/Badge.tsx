
interface BadgeProps {
    children: React.ReactNode;
    color?: "gray" | "green" | "red" | "yellow" | "blue";
}

const colors = {
    gray: "bg-slate-100 text-slate-700",
    green: "bg-green-100 text-green-700",
    red: "bg-red-100 text-red-700",
    yellow: "bg-yellow-100 text-yellow-700",
    blue: "bg-blue-100 text-blue-700",
};

export default function Badge({
    children,
    color = "gray",
}: BadgeProps) {
    return (
        <span
            className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${colors[color]}`}
        >
            {children}
        </span>
    );
}