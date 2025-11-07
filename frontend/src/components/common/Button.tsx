//src/components/common/Button.tsx
interface ButtonProps {
    name: string;
    variant?: 'primary' | 'secondary' | 'success' | 'danger';
    onClick: () => void;
    disabled?: boolean;
    loading?: boolean;
}

const variantClasses = {
    primary: 'bg-blue-500 hover:bg-blue-600',
    secondary: 'bg-gray-500 hover:bg-gray-600',
    success: 'bg-green-500 hover:bg-green-600',
    danger: 'bg-red-500 hover:bg-red-600',
};

export default function Button({ name, variant = 'primary', onClick, disabled, loading }: ButtonProps) {
    const baseClasses = "px-6 py-3 rounded-lg font-medium text-white";
    const disabledClasses = "bg-gray-300 text-gray-500 cursor-not-allowed";

    return(
        <button onClick={onClick}
        disabled={disabled || loading}
        className={`${baseClasses} ${disabled || loading ? disabledClasses: variantClasses[variant]}`}>
            {loading ? '...' : name}
        </button>
    )
};