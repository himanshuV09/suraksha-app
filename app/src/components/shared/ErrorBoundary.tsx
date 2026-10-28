import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
    children: ReactNode;
}

interface State {
    error: Error | null;
}

/** Shows a recoverable error panel instead of a blank window. */
export default class ErrorBoundary extends Component<Props, State> {
    state: State = { error: null };

    static getDerivedStateFromError(error: Error): State {
        return { error };
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error("Unhandled UI error", error, info.componentStack);
    }

    render() {
        if (!this.state.error) {
            return this.props.children;
        }
        return (
            <div role="alert" className="m-8 rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-800">
                <h2 className="mb-2 text-base font-semibold">This screen hit an unexpected error.</h2>
                <p className="mb-4 font-mono text-xs">{this.state.error.message}</p>
                <button
                    type="button"
                    onClick={() => this.setState({ error: null })}
                    className="rounded-md border border-red-300 bg-white px-3 py-1.5 hover:bg-red-100"
                >
                    Try again
                </button>
            </div>
        );
    }
}
